import os
import re
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from azure.cosmos import CosmosClient
from pydantic import BaseModel

from db_connection import get_connection

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"

OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
CHAT_DEPLOYMENT = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]

COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DATABASE = os.environ["COSMOS_DATABASE"]
COSMOS_CONTAINER = os.environ["COSMOS_CONTAINER"]

openai_client = OpenAI(base_url=OPENAI_ENDPOINT, api_key=OPENAI_API_KEY)
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
container = cosmos_client.get_database_client(COSMOS_DATABASE).get_container_client(COSMOS_CONTAINER)

app = FastAPI(title="POC Atendimento IA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PerguntaRequest(BaseModel):
    pergunta: str
    cliente_id: str | None = None
    top_k: int = 5


class Fonte(BaseModel):
    texto: str
    origem: str
    clientId: str
    clientNome: str | None = None
    score: float
    dadosSql: dict | None = None


class PerguntaResponse(BaseModel):
    resposta: str
    fontes: list[Fonte]
    clienteId: str | None = None


class ClienteResumo(BaseModel):
    clienteId: int
    nome: str


class AtendimentoResumo(BaseModel):
    numeroChamado: str
    assunto: str | None = None
    status: str | None = None
    dataAbertura: str | None = None


class StatusCount(BaseModel):
    status: str
    total: int


class AssuntoCount(BaseModel):
    assunto: str
    total: int


class AtendimentosClienteResponse(BaseModel):
    clienteId: int
    clienteNome: str
    clienteEmail: str | None = None
    clienteTelefone: str | None = None
    clienteDocumento: str | None = None
    total: int
    porStatus: list[StatusCount]
    porAssunto: list[AssuntoCount]
    atendimentos: list[AtendimentoResumo]


CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def extrair_cpf(texto: str) -> str | None:
    match = CPF_PATTERN.search(texto)
    if not match:
        return None
    return re.sub(r"\D", "", match.group())


def buscar_cliente_por_cpf(cpf: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ClienteId, Nome
            FROM dbo.ClientesCadastro
            WHERE REPLACE(REPLACE(Documento, '.', ''), '-', '') = ?
            """,
            cpf,
        )
        row = cursor.fetchone()
        return {"clienteId": row.ClienteId, "nome": row.Nome} if row else None


def gerar_embedding(texto: str) -> list[float]:
    response = openai_client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=texto)
    return response.data[0].embedding


def buscar_chunks_relevantes(query_vector: list[float], top_k: int, cliente_id: str | None) -> list[dict]:
    query = (
        "SELECT TOP @top_k c.texto, c.origem, c.origemId, c.clientId, c.clientNome, "
        "VectorDistance(c.vector, @queryVector) AS score "
        "FROM c"
    )
    parameters = [
        {"name": "@top_k", "value": top_k},
        {"name": "@queryVector", "value": query_vector},
    ]
    if cliente_id:
        query += " WHERE c.clientId = @clienteId"
        parameters.append({"name": "@clienteId", "value": cliente_id})
    query += " ORDER BY VectorDistance(c.vector, @queryVector)"

    return list(
        container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
    )


def enriquecer_com_sql(chunks: list[dict]) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        for chunk in chunks:
            if chunk["origem"] == "Topdesk":
                cursor.execute(
                    """
                    SELECT NumeroChamado, Assunto, Status, DataAbertura, DataFechamento
                    FROM dbo.AtendimentosTopdesk
                    WHERE AtendimentoId = ?
                    """,
                    chunk["origemId"],
                )
                row = cursor.fetchone()
                if row:
                    chunk["dadosSql"] = {
                        "numeroChamado": row.NumeroChamado,
                        "assunto": row.Assunto,
                        "status": row.Status,
                        "dataAbertura": row.DataAbertura.isoformat() if row.DataAbertura else None,
                        "dataFechamento": row.DataFechamento.isoformat() if row.DataFechamento else None,
                    }
            elif chunk["origem"] == "Transcricao":
                cursor.execute(
                    """
                    SELECT DataLigacao, DuracaoSegundos
                    FROM dbo.TranscricoesLigacoes
                    WHERE TranscricaoId = ?
                    """,
                    chunk["origemId"],
                )
                row = cursor.fetchone()
                if row:
                    chunk["dadosSql"] = {
                        "dataLigacao": row.DataLigacao.isoformat() if row.DataLigacao else None,
                        "duracaoSegundos": row.DuracaoSegundos,
                    }


def montar_contexto(chunks: list[dict]) -> str:
    partes = []
    for chunk in chunks:
        linha = f"- {chunk['texto']}"
        dados = chunk.get("dadosSql")
        if dados:
            detalhes = ", ".join(f"{k}: {v}" for k, v in dados.items() if v is not None)
            linha += f" [Dados atuais no sistema: {detalhes}]"
        partes.append(linha)
    return "\n\n".join(partes)


def gerar_resposta(pergunta: str, contexto: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Você é um assistente que responde perguntas sobre atendimentos ao cliente "
                "com base apenas no contexto fornecido. Se a resposta não estiver no contexto, "
                "diga que não possui essa informação. Se o contexto indicar que um cliente já "
                "foi identificado a partir de um CPF, e-mail ou outro identificador informado na "
                "pergunta, trate qualquer referência a esse identificador na pergunta como uma "
                "referência a esse cliente e responda normalmente com os dados dele."
            ),
        },
        {"role": "user", "content": f"Contexto:\n{contexto}\n\nPergunta: {pergunta}"},
    ]
    response = openai_client.chat.completions.create(model=CHAT_DEPLOYMENT, messages=messages)
    return response.choices[0].message.content


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/clientes", response_model=list[ClienteResumo])
def buscar_clientes(q: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP 10 ClienteId, Nome
            FROM dbo.ClientesCadastro
            WHERE Nome LIKE ?
            ORDER BY Nome
            """,
            f"%{q}%",
        )
        return [{"clienteId": row.ClienteId, "nome": row.Nome} for row in cursor.fetchall()]


@app.get("/clientes/{cliente_id}/atendimentos", response_model=AtendimentosClienteResponse)
def atendimentos_por_cliente(cliente_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Nome, Email, Telefone, Documento FROM dbo.ClientesCadastro WHERE ClienteId = ?",
            cliente_id,
        )
        cliente = cursor.fetchone()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        cursor.execute(
            """
            SELECT NumeroChamado, Assunto, Status, DataAbertura
            FROM dbo.AtendimentosTopdesk
            WHERE ClienteId = ?
            ORDER BY DataAbertura DESC
            """,
            cliente_id,
        )
        atendimentos = [
            {
                "numeroChamado": row.NumeroChamado,
                "assunto": row.Assunto,
                "status": row.Status,
                "dataAbertura": row.DataAbertura.isoformat() if row.DataAbertura else None,
            }
            for row in cursor.fetchall()
        ]

    contagem_status = Counter(a["status"] or "Sem status" for a in atendimentos)
    por_status = [{"status": status, "total": total} for status, total in contagem_status.most_common()]

    contagem_assunto = Counter(a["assunto"] or "Sem assunto" for a in atendimentos)
    top_assuntos = contagem_assunto.most_common(8)
    outros_total = sum(total for _, total in contagem_assunto.most_common()[8:])
    por_assunto = [{"assunto": assunto, "total": total} for assunto, total in top_assuntos]
    if outros_total > 0:
        por_assunto.append({"assunto": "Outros", "total": outros_total})

    return {
        "clienteId": cliente_id,
        "clienteNome": cliente.Nome,
        "clienteEmail": cliente.Email,
        "clienteTelefone": cliente.Telefone,
        "clienteDocumento": cliente.Documento,
        "total": len(atendimentos),
        "porStatus": por_status,
        "porAssunto": por_assunto,
        "atendimentos": atendimentos,
    }


@app.post("/perguntar", response_model=PerguntaResponse)
def perguntar(request: PerguntaRequest):
    cliente_id = request.cliente_id
    cliente_encontrado = None

    cpf = extrair_cpf(request.pergunta)
    if cpf:
        cliente_encontrado = buscar_cliente_por_cpf(cpf)
        if cliente_encontrado:
            cliente_id = str(cliente_encontrado["clienteId"])

    query_vector = gerar_embedding(request.pergunta)
    chunks = buscar_chunks_relevantes(query_vector, request.top_k, cliente_id)
    enriquecer_com_sql(chunks)
    contexto = montar_contexto(chunks)
    if cliente_encontrado:
        contexto = (
            f"O CPF mencionado na pergunta corresponde ao cliente: {cliente_encontrado['nome']}.\n\n{contexto}"
        )
    resposta = gerar_resposta(request.pergunta, contexto)

    return {
        "resposta": resposta,
        "fontes": chunks,
        "clienteId": str(cliente_encontrado["clienteId"]) if cliente_encontrado else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
