import os

from dotenv import load_dotenv
from openai import OpenAI
from azure.cosmos import CosmosClient

from db_connection import get_connection

load_dotenv()

OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]

COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DATABASE = os.environ["COSMOS_DATABASE"]
COSMOS_CONTAINER = os.environ["COSMOS_CONTAINER"]

CHUNK_MAX_CHARS = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks


def fetch_consolidado_rows(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tc.ConsolidadoId, tc.ClienteId, tc.Origem, tc.OrigemId, tc.Conteudo, tc.DataReferencia,
               cc.Nome AS ClienteNome
        FROM dbo.TabelaConsolidada tc
        LEFT JOIN dbo.ClientesCadastro cc ON cc.ClienteId = tc.ClienteId
        """
    )
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_documents(rows: list[dict]) -> list[dict]:
    documents = []
    for row in rows:
        nome = row["ClienteNome"]
        texto_completo = f"Cliente: {nome}. {row['Conteudo']}" if nome else row["Conteudo"]
        chunks = chunk_text(texto_completo)
        client_id = str(row["ClienteId"]) if row["ClienteId"] is not None else "sem-cliente"
        for i, chunk in enumerate(chunks):
            documents.append(
                {
                    "id": f"{row['ConsolidadoId']}-{i}",
                    "clientId": client_id,
                    "clientNome": nome,
                    "consolidadoId": row["ConsolidadoId"],
                    "origem": row["Origem"],
                    "origemId": row["OrigemId"],
                    "chunkIndex": i,
                    "texto": chunk,
                    "dataReferencia": row["DataReferencia"].isoformat() if row["DataReferencia"] else None,
                }
            )
    return documents


def embed_documents(openai_client: OpenAI, documents: list[dict]) -> None:
    for doc in documents:
        response = openai_client.embeddings.create(
            model=EMBEDDING_DEPLOYMENT,
            input=doc["texto"],
        )
        doc["vector"] = response.data[0].embedding


def upsert_documents(container, documents: list[dict]) -> None:
    for doc in documents:
        container.upsert_item(doc)


def run():
    with get_connection() as conn:
        rows = fetch_consolidado_rows(conn)
    print(f"{len(rows)} registros lidos de dbo.TabelaConsolidada.")

    documents = build_documents(rows)
    print(f"{len(documents)} chunks gerados.")

    openai_client = OpenAI(base_url=OPENAI_ENDPOINT, api_key=OPENAI_API_KEY)
    embed_documents(openai_client, documents)
    print("Embeddings gerados.")

    cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    database = cosmos_client.get_database_client(COSMOS_DATABASE)
    container = database.get_container_client(COSMOS_CONTAINER)
    upsert_documents(container, documents)
    print(f"{len(documents)} chunks gravados no Cosmos DB.")


if __name__ == "__main__":
    run()
