from datetime import datetime
from pathlib import Path

import openpyxl

from db_connection import get_connection

BASE_DIR = Path(__file__).parent
CLIENTES_FILE = BASE_DIR / "clientes topdesk.xlsx"
ATENDIMENTOS_FILE = BASE_DIR / "atendimentos topdesk.xlsx"
TRANSCRICOES_FILE = BASE_DIR / "transcrições.xlsx"

DATE_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M")


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_rows(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter)
    return [dict(zip(header, row)) for row in rows_iter]


def carregar_clientes_existentes(cursor) -> dict:
    cursor.execute("SELECT ClienteId, Documento FROM dbo.ClientesCadastro WHERE Documento IS NOT NULL")
    return {documento: cliente_id for cliente_id, documento in cursor.fetchall()}


def inserir_cliente(cursor, nome: str | None, documento: str | None, email: str | None,
                     telefone: str | None, data_cadastro: datetime | None) -> int:
    cursor.execute(
        """
        INSERT INTO dbo.ClientesCadastro (Nome, Documento, Email, Telefone, DataCadastro)
        OUTPUT INSERTED.ClienteId
        VALUES (?, ?, ?, ?, COALESCE(?, SYSUTCDATETIME()))
        """,
        nome or "Desconhecido",
        documento,
        email,
        telefone,
        data_cadastro,
    )
    return cursor.fetchone()[0]


def importar_clientes(cursor, clientes_map: dict) -> int:
    linhas = load_rows(CLIENTES_FILE)
    inseridos = 0
    for linha in linhas:
        cpf = clean_text(linha.get("CPF"))
        if cpf and cpf in clientes_map:
            continue
        cliente_id = inserir_cliente(
            cursor,
            clean_text(linha.get("NOME")),
            cpf,
            clean_text(linha.get("EMAIL")),
            clean_text(linha.get("Telefone")),
            parse_datetime(linha.get("DATA_DE_CRIACAO")),
        )
        if cpf:
            clientes_map[cpf] = cliente_id
        inseridos += 1
    return inseridos


def carregar_protocolos_existentes(cursor) -> set:
    cursor.execute("SELECT NumeroChamado FROM dbo.AtendimentosTopdesk")
    return {row[0] for row in cursor.fetchall()}


def importar_atendimentos(cursor, clientes_map: dict, protocolos_existentes: set) -> tuple[int, int]:
    linhas = load_rows(ATENDIMENTOS_FILE)
    atendimentos_inseridos = 0
    consolidados_inseridos = 0

    for linha in linhas:
        protocolo = clean_text(linha.get("PROTOCOLO"))
        if not protocolo or protocolo in protocolos_existentes:
            continue

        cpf = clean_text(linha.get("CPF"))
        cliente_id = clientes_map.get(cpf) if cpf else None
        if cpf and cliente_id is None:
            cliente_id = inserir_cliente(cursor, clean_text(linha.get("NOME")), cpf,
                                          clean_text(linha.get("EMAIL")), clean_text(linha.get("TELEFONE")), None)
            clientes_map[cpf] = cliente_id

        assunto = clean_text(linha.get("CATEGORIA"))
        descricao = clean_text(linha.get("BREVE_DESCRICAO"))
        status = clean_text(linha.get("STATUS"))
        data_abertura = parse_datetime(linha.get("DATA_DE_CRIACAO"))
        data_fechamento = parse_datetime(linha.get("DATA_DE_CONCLUSAO"))

        cursor.execute(
            """
            INSERT INTO dbo.AtendimentosTopdesk
                (ClienteId, NumeroChamado, Assunto, Descricao, Status, DataAbertura, DataFechamento)
            OUTPUT INSERTED.AtendimentoId
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            cliente_id, protocolo, assunto, descricao, status, data_abertura, data_fechamento,
        )
        atendimento_id = cursor.fetchone()[0]
        protocolos_existentes.add(protocolo)
        atendimentos_inseridos += 1

        conteudo = f"Chamado {protocolo} - {assunto or 'Sem categoria'}: {descricao or ''}. Status: {status or 'Desconhecido'}."
        cursor.execute(
            """
            INSERT INTO dbo.TabelaConsolidada (ClienteId, Origem, OrigemId, Conteudo)
            VALUES (?, 'Topdesk', ?, ?)
            """,
            cliente_id, atendimento_id, conteudo,
        )
        consolidados_inseridos += 1

    return atendimentos_inseridos, consolidados_inseridos


def importar_transcricoes(cursor, clientes_map: dict) -> tuple[int, int]:
    linhas = load_rows(TRANSCRICOES_FILE)
    transcricoes_inseridas = 0
    consolidados_inseridos = 0

    for linha in linhas:
        transcricao = clean_text(linha.get("TRANSCRICAO_CORRIGIDA")) or clean_text(linha.get("TRANSCRICAO_ORIGINAL"))
        if not transcricao:
            continue

        cpf = clean_text(linha.get("cpf"))
        cliente_id = clientes_map.get(cpf) if cpf else None
        if cpf and cliente_id is None:
            cliente_id = inserir_cliente(cursor, None, cpf, None, None, None)
            clientes_map[cpf] = cliente_id

        data_ligacao = parse_datetime(linha.get("DATA_CARGA"))

        cursor.execute(
            """
            INSERT INTO dbo.TranscricoesLigacoes (ClienteId, AtendimentoId, Transcricao, DataLigacao, DuracaoSegundos)
            OUTPUT INSERTED.TranscricaoId
            VALUES (?, NULL, ?, ?, NULL)
            """,
            cliente_id, transcricao, data_ligacao,
        )
        transcricao_id = cursor.fetchone()[0]
        transcricoes_inseridas += 1

        cursor.execute(
            """
            INSERT INTO dbo.TabelaConsolidada (ClienteId, Origem, OrigemId, Conteudo)
            VALUES (?, 'Transcricao', ?, ?)
            """,
            cliente_id, transcricao_id, transcricao,
        )
        consolidados_inseridos += 1

    return transcricoes_inseridas, consolidados_inseridos


def run():
    with get_connection() as conn:
        cursor = conn.cursor()

        clientes_map = carregar_clientes_existentes(cursor)
        novos_clientes = importar_clientes(cursor, clientes_map)
        conn.commit()
        print(f"{novos_clientes} clientes importados (total no mapa: {len(clientes_map)}).")

        protocolos_existentes = carregar_protocolos_existentes(cursor)
        atendimentos_inseridos, consolidados_atend = importar_atendimentos(cursor, clientes_map, protocolos_existentes)
        conn.commit()
        print(f"{atendimentos_inseridos} atendimentos importados ({consolidados_atend} registros consolidados).")

        transcricoes_inseridas, consolidados_transc = importar_transcricoes(cursor, clientes_map)
        conn.commit()
        print(f"{transcricoes_inseridas} transcrições importadas ({consolidados_transc} registros consolidados).")


if __name__ == "__main__":
    run()
