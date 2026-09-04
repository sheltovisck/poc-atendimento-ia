-- Estrutura inicial baseada em POC_Atendimento_IA_Resumo_Conversa.md
-- Fontes de Dados: Cadastro de Clientes, Atendimentos TOPdesk, Transcrições de ligações
-- + Tabela Consolidada (entrada do pipeline de chunking/embeddings)

IF OBJECT_ID('dbo.ClientesCadastro', 'U') IS NULL
CREATE TABLE dbo.ClientesCadastro (
    ClienteId       INT IDENTITY(1,1) PRIMARY KEY,
    Nome            NVARCHAR(200)   NOT NULL,
    Documento       NVARCHAR(20)    NULL,
    Email           NVARCHAR(200)   NULL,
    Telefone        NVARCHAR(30)    NULL,
    DataCadastro    DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('dbo.AtendimentosTopdesk', 'U') IS NULL
CREATE TABLE dbo.AtendimentosTopdesk (
    AtendimentoId   INT IDENTITY(1,1) PRIMARY KEY,
    ClienteId       INT             NULL REFERENCES dbo.ClientesCadastro(ClienteId),
    NumeroChamado   NVARCHAR(50)    NOT NULL,
    Assunto         NVARCHAR(300)   NULL,
    Descricao       NVARCHAR(MAX)   NULL,
    Status          NVARCHAR(50)    NULL,
    DataAbertura    DATETIME2       NULL,
    DataFechamento  DATETIME2       NULL
);

IF OBJECT_ID('dbo.TranscricoesLigacoes', 'U') IS NULL
CREATE TABLE dbo.TranscricoesLigacoes (
    TranscricaoId   INT IDENTITY(1,1) PRIMARY KEY,
    ClienteId       INT             NULL REFERENCES dbo.ClientesCadastro(ClienteId),
    AtendimentoId   INT             NULL REFERENCES dbo.AtendimentosTopdesk(AtendimentoId),
    Transcricao     NVARCHAR(MAX)   NULL,
    DataLigacao     DATETIME2       NULL,
    DuracaoSegundos INT             NULL
);

IF OBJECT_ID('dbo.TabelaConsolidada', 'U') IS NULL
CREATE TABLE dbo.TabelaConsolidada (
    ConsolidadoId   INT IDENTITY(1,1) PRIMARY KEY,
    ClienteId       INT             NULL REFERENCES dbo.ClientesCadastro(ClienteId),
    Origem          NVARCHAR(50)    NOT NULL,   -- 'Cadastro' | 'Topdesk' | 'Transcricao'
    OrigemId        INT             NULL,       -- Id do registro na tabela de origem
    Conteudo        NVARCHAR(MAX)   NOT NULL,   -- texto pronto para chunking/embeddings
    DataReferencia  DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME()
);
