# Projeto POC - Atendimento com IA

## Objetivo

Construir uma POC utilizando Azure SQL Database, Azure OpenAI, Azure
Cosmos DB e uma aplicação web para consultas inteligentes sobre
atendimentos.

## Arquitetura

``` text
Arquivos/SQL Server
        │
        ▼
Azure SQL Database
        │
        ▼
Tabela Consolidada
        │
        ▼
Python
 ├─ Chunking
 ├─ Embeddings
 └─ Cosmos DB
        │
        ▼
Cosmos DB Vector Search
        │
        ▼
Azure OpenAI (Chat)
        │
        ▼
FastAPI
        │
        ▼
Aplicação Web
```

## Fontes de Dados

-   Cadastro de Clientes
-   Atendimentos TOPdesk
-   Transcrições de ligações

## Conceitos

### Chunk

Pequenos trechos de um documento utilizados para melhorar a recuperação
de contexto.

### Embedding

Representação vetorial do significado de um texto, utilizada para busca
semântica.

## Fluxo

1.  Ler Azure SQL.
2.  Criar chunks.
3.  Gerar embeddings.
4.  Gravar Cosmos DB.
5.  Receber pergunta.
6.  Gerar embedding da pergunta.
7.  Buscar documentos semelhantes.
8.  Enviar contexto ao modelo de chat.
9.  Exibir resposta.

## Recursos Azure

-   Azure SQL Database
-   Azure OpenAI
-   Azure Cosmos DB
-   Azure App Service
-   Microsoft Fabric (produção)

## Próximos Passos

-   Criar recursos Azure.
-   Importar planilhas.
-   Vetorizar dados.
-   Construir API FastAPI.
-   Criar interface web.
-   Publicar.
