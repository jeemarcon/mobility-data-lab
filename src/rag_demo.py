import chromadb
import glob
import os
import anthropic
import json

# cliente da API da Claude, usado na etapa de "generation" do RAG (responder com contexto)
client_llm = anthropic.Anthropic()

# cliente do Chroma: banco vetorial local, roda em memória, sem precisar de servidor externo
chroma_client = chromadb.Client()

# "collection" é onde os documentos indexados (com seus embeddings) ficam armazenados
collection = chroma_client.create_collection(name="project_docs")


def load_documents() -> list[dict]:
    """Carrega README como um documento único, e cada regra de qualidade
    como um documento individual — isso é 'chunking': indexar por unidade
    pequena e específica, não por arquivo inteiro.
    """
    docs = []

    # README continua como documento único: é curto e genérico o suficiente
    if os.path.exists("README.md"):
        with open("README.md") as f:
            docs.append({"id": "README.md", "text": f.read(), "source": "README.md"})

    # cada arquivo de regras vira VÁRIOS documentos pequenos, um por regra
    for path in glob.glob("docs/quality_rules_*.json"):
        table_name = os.path.basename(path).replace("quality_rules_", "").replace(".json", "")
        with open(path) as f:
            rules = json.load(f)

        for i, rule in enumerate(rules):
            # cada chunk vira uma frase curta e autocontida — mais fácil de "casar" com a pergunta
            text = f"Tabela {table_name}, coluna {rule['column']}: regra '{rule['rule']}' — {rule['reason']}"
            docs.append({"id": f"{path}_{i}", "text": text, "source": path})

    return docs


def index_documents(docs: list[dict]):
    """Adiciona os documentos à coleção do Chroma (gera embeddings automaticamente)."""
    # .add() já cuida de gerar os embeddings internamente — não precisamos chamar isso manualmente
    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[{"source": d["source"]} for d in docs],  # metadata guarda de onde veio cada trecho
    )


def ask(question: str, n_results: int = 15) -> str:
    """Busca os documentos mais relevantes e usa como contexto para responder.

    Args:
        question: pergunta do usuário.
        n_results: quantos documentos recuperar.

    Returns:
        Resposta gerada pelo Claude com base nos documentos recuperados.
    """
    # etapa de RETRIEVAL: busca por similaridade vetorial, não por palavra-chave
    results = collection.query(query_texts=[question], n_results=n_results)

    # junta os documentos recuperados num único bloco de texto pra injetar no prompt
    retrieved = "\n\n---\n\n".join(results["documents"][0])
    sources = [m["source"] for m in results["metadatas"][0]]

    # log de auditoria: mostra de onde veio o contexto usado na resposta
    print(f"  (contexto recuperado de: {sources})")

    # etapa de AUGMENTED GENERATION: o contexto recuperado é injetado antes da pergunta
    prompt = f"""Use o contexto abaixo para responder à pergunta. Se a resposta não
estiver no contexto, diga que não sabe com base nos documentos disponíveis.

Contexto:
{retrieved}

Pergunta: {question}"""

    response = client_llm.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        temperature=0.0,  # baixa, já que queremos precisão factual, não criatividade
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    docs = load_documents()
    print(f"Documentos carregados: {[d['source'] for d in docs]}")

    # indexação acontece uma vez, no início — em produção isso seria feito só quando os docs mudassem
    index_documents(docs)

    # perguntas de teste pra validar se o RAG está recuperando o contexto certo
    perguntas = [
        "Quais tabelas esse projeto gera?",
        "Quais regras de qualidade existem para a coluna distance_km?",
    ]

    for q in perguntas:
        print(f"\nPergunta: {q}")
        print(f"Resposta: {ask(q)}")