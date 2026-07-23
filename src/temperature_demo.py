import anthropic

client = anthropic.Anthropic()  # pega a API key da variável de ambiente ANTHROPIC_API_KEY

prompt = "Escreva um slogan curto e criativo para um app de mobilidade urbana (corridas de carro, bike e patinete). Sugira apenas uma frase e nada mais."

for temp in [0.0, 1.0]:
    print(f"\n--- Temperature: {temp} ---")
    for _ in range(2):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            temperature=temp,
            messages=[{"role": "user", "content": prompt}]
        )
        print(response.content[0].text)