import json
import random


def gen_cpf():
    while True:
        n = [random.randint(0, 9) for _ in range(9)]
        if len(set(n)) == 1:
            continue
        d1 = (sum((10 - i) * n[i] for i in range(9)) * 10) % 11
        d1 = 0 if d1 >= 10 else d1
        n.append(d1)
        d2 = (sum((11 - i) * n[i] for i in range(10)) * 10) % 11
        d2 = 0 if d2 >= 10 else d2
        n.append(d2)
        digits = "".join(map(str, n))
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def gen_phone():
    ddd = random.choice(["81", "87", "83", "82", "86", "84", "85", "88", "89"])
    part1 = "9" + "".join(str(random.randint(0, 9)) for _ in range(4))
    part2 = "".join(str(random.randint(0, 9)) for _ in range(4))
    return f"{ddd}-{part1}.{part2}"


names = [
    "Abelardo Freitas", "Adailton Souza", "Ademar Costa", "Adilson Santos", "Adriano Lima",
    "Agostinho Ramos", "Alberto Ferreira", "Aldemir Nunes", "Alexsandro Moura", "Alinton Silva",
    "Altamiro Gomes", "Aluisio Barbosa", "Americo Oliveira", "Anisio Pereira", "Antonio Azevedo",
    "Ariovaldo Cunha", "Aristeu Cavalcanti", "Armando Lopes", "Arnaldo Rodrigues", "Augusto Melo",
    "Aurindo Carvalho", "Baltazar Mendes", "Benedito Alves", "Benvindo Cruz", "Bernardino Farias",
    "Brigido Monteiro", "Candido Araujo", "Caetano Ribeiro", "Claudio Macedo", "Clovis Andrade",
    "Crisostomo Vieira", "Dagoberto Nascimento", "Daltro Cardoso", "Danivio Sousa", "Darcisio Leite",
    "Darcy Medeiros", "Demerval Torres", "Dinalvo Lima", "Dirceu Tavares", "Divaldo Correia",
    "Domingos Fernandes", "Dorival Guimaraes", "Edivaldo Pinto", "Edmilson Batista", "Edilberto Campos",
    "Egidio Martins", "Eladio Pacheco", "Elisio Siqueira", "Elmano Queiroz", "Elvecio Borges",
    "Emanoel Teixeira", "Ermindo Brito", "Ernando Duarte", "Estenio Castro", "Eugenio Fonseca",
    "Everaldo Magalhaes", "Evaldo Pinheiro", "Ezequiel Rocha", "Fabio Vasconcelos", "Fanuel Almeida",
    "Feliciano Nogueira", "Felino Coelho", "Firmino Bezerra", "Flavio Alencar", "Florindo Rego",
    "Fontes Sampaio", "Fortunato Dias", "Francinaldo Xavier", "Fulgencio Lacerda", "Galdino Marques",
    "Genivaldo Luz", "Gervasio Paiva", "Gilberto Neto", "Gilmar Saraiva", "Gilson Morais",
    "Givanildo Freire", "Gladiston Sales", "Gledson Feitosa", "Goncalo Menezes", "Gregorio Leal",
]

teams = [
    {"id": 6, "name": "Cajueiro BJJ"},
    {"id": 5, "name": "Casa Caiu BJJ"},
    {"id": 2, "name": "Gio BJJ"},
    {"id": 4, "name": "OlindaBJJ"},
    {"id": 8, "name": "Pesqueira BJJ"},
    {"id": 1, "name": "Progress BJJ"},
    {"id": 3, "name": "Recife BJJ"},
    {"id": 7, "name": "Vida Bandida BJJ"},
]

used_cpfs: set[str] = set()
athletes = []

for i, name in enumerate(names):
    while True:
        cpf = gen_cpf()
        if cpf not in used_cpfs:
            used_cpfs.add(cpf)
            break
    slug = name.lower().replace(" ", ".")
    email = f"{slug}.{i + 1}@bjj.com"
    team = teams[i % len(teams)]
    athletes.append({
        "name": name,
        "cpf": cpf,
        "email": email,
        "phone": gen_phone(),
        "sex": "male",
        "team_id": team["id"],
        "belt": "white",
        "graduation_date": "1984-04-17",
        "birth_date": "1984-04-17",
    })

output = "atletas_bulk.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(athletes, f, ensure_ascii=False, indent=2)

print(f"Gerado: {len(athletes)} atletas -> {output}")
