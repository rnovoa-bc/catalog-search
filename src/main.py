import os
from dotenv import load_dotenv
from google import genai
import requests
from urllib.parse import quote
import mariadb

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
tools = [
]

generation_config = {
    "temperature": 1,
    "max_output_tokens": 10000,

}

def cofre_indexing():
    mariadb_connection = mariadb.connect(
        host=os.getenv("COFRE_HOST"),
        user=os.getenv("COFRE_USER"),
        password=os.getenv("COFRE_PASSWORD"),
        database=os.getenv("COFRE_DB")
    )
    cursor = mariadb_connection.cursor()
    cursor.execute("SELECT * FROM some_table")  # Replace 'some_table' with your actual table name
def get_gemini_response(user_prompt, alternatives=True):
    prompt = f"""
    Analitza la següent consulta de l'usuari d'una biblioteca: '{user_prompt}'.
    Actua com un bibliotecari expert en recuperació d'informació per a un catàleg (Ex Libris Primo). Has d'intentar ser el més espcífic possible.
    Si no pots generar una queery precisa presente 3 possibles alternatives per tal de eliminar l'ambiguitat.
    Fes el següent:

    1. Genera una query optimitzada per a Primo (amb operadors booleans si escau, com OR, o termes clau d'àmbit general/materia, evitant paraules buides).
    2. Si no pots generar una query precisa, presenta 2 O 3 possibles alternatives per tal de eliminar l'ambiguitat. En llenguatge humà per a l'usuari.
    
    Torna-m'ho estrictament en format TEXT amb aquest format:
    1. Quan creus que saps la query correcta, utilitza el següent format: <camp_1>,<precisio_1>,<valor_1>[,<oprador_1>][;<camp_2>,<precisio_2>,<valor_2>[,<oprador_2>;]...] on
    con camp pot valdre: any,title,creator o sub (generalment farem servir any)
    precisio pot valdre: exact,contains (generalment farem servir contains)
    valor és el terme que es vol cercar
    operador pot valdre: AND, OR, NOT i especifiquen con interactuarem amb els següents termes si i són presents
    2. Si no pots generar una query precisa, utilitza el següent format per a les alternatives: Tria una:<alternativa_1>;<alternativa_2>;[alternativa_3] on cada alternativa és una descripció en llenguatge humà de la possible query.
    """ if alternatives else """
    Analitza la següent consulta de l'usuari d'una biblioteca: '{user_prompt}'.
    Actua com un bibliotecari expert en recuperació d'informació per a un catàleg (Ex Libris Primo). Has d'intentar ser el més espcífic possible.
    Fes el següent:

    1. Genera una query optimitzada per a Primo (amb operadors booleans si escau, com OR, o termes clau d'àmbit general/materia, evitant paraules buides).
    
    Torna-m'ho estrictament en format TEXT amb aquest format:
    1. Quan creus que saps la query correcta, utilitza el següent format: <camp_1>,<precisio_1>,<valor_1>[,<oprador_1>][;<camp_2>,<precisio_2>,<valor_2>[,<oprador_2>;]...] on
    con camp pot valdre: any,title,creator o sub (generalment farem servir any)
    precisio pot valdre: exact,contains (generalment farem servir contains)
    valor és el terme que es vol cercar
    operador pot valdre: AND, OR, NOT i especifiquen con interactuarem amb els següents termes si i són presents
    """
    interaction = client.interactions.create(
        model='models/gemini-3-flash-preview',
        input=prompt,
        tools=tools,
        generation_config=generation_config,
    )
    # Extraiem el text de manera segura
    last_step = interaction.steps[-1]
    if last_step.content and len(last_step.content) > 0:
        return last_step.content[0].text
    return ""

def get_docs(query):
    """
    Funció per obtenir els títols d'un registre a partir de l'encapçalament.
    """
    url = "https://api-eu.hosted.exlibrisgroup.com/primo/v1/search"

    params = {
        "vid": "34CSUC_BC:VU1",
        "tab": "Everythin34BC_CCUC",
        "scope": "MyInst_and_CI",
        "q": query,
        "newspapersActive": "true",
        "pcAvailability": "true",
        "lang": "ca_ES",
        "offset": 0,
        "limit": 10,
        "sort": "rank",
        "getMore": 0,
        "conVoc": "true",
        "inst": "34CSUC_BC",
        "skipDelivery": "true",
        "disableSplitFacets": "true",
        "apikey": os.getenv("PRIMO_API_KEY")
    }
    titols = []
    ids = []
    descripcions = []
    try:
        resposta = requests.get(url, params=params)
        resposta.raise_for_status()
        dades = resposta.json()
        for document in dades.get("docs", []):
            titol = document["pnx"]["display"]["title"][0]
            titols.append(titol)
            ids.append(document["pnx"]["control"]["recordid"][0])

            if "description" in document["pnx"]["display"]:
                descripcions.append(". ".join(document["pnx"]["display"]["description"]))
            else:
                descripcions.append("")

    except Exception as e:
        print(f"Error obtenint títols per {query}: {e}")
    return (titols, ids,descripcions)

def main():

    # Bucle principal per demanar a l'usuari què vol cercar
    while True:
        user_input = input("Que voleu cercar (intro per finalitzar): ")
        if not user_input:
            print("\nFins aviat!\n")
            break
        print(f"Buscant: {user_input}")
        response = get_gemini_response(user_input, True)
        print(f"Resposta de Gemini: {response}")
        if len(response) > 0:
            if response.startswith("Tria una:"):
                alternatives = response[len("Tria una:"):].split(";")
                print("S'han detectat múltiples alternatives per a la consulta:")
                for i, alt in enumerate(alternatives):
                    print(f"{i+1}. {alt}")
                choice = input(f"Trieu una alternativa (1-{len(alternatives)}): ")
                if choice.isdigit() and 1 <= int(choice) <= len(alternatives):
                    response = get_gemini_response(alternatives[int(choice) - 1], False)
                else:
                    print("Elecció no vàlida. Tornant a demanar la consulta.")
                    continue
            titols, ids, descripcions = get_docs(response)
            for titol, id, descripcio in zip(titols, ids, descripcions):
                print(f"Títol: {titol}")
                print(f"URL: https://explora.bnc.cat/discovery/fulldisplay?docid={id}&context=L&vid=34CSUC_BC:VU1&lang=ca&search_scope=MyInst_and_CI")
                print(f"Descripció: {descripcio}")
                print()
        else:
            print("No s'han trobat documents per a la consulta.")

        


if __name__ == "__main__":
    main()