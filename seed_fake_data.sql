-- Dados fictícios para teste do pipeline (chunking/embeddings)
-- Rodar após create_tables.sql

-- 1) Clientes
INSERT INTO dbo.ClientesCadastro (Nome, Documento, Email, Telefone) VALUES
('Ana Beatriz Souza',   '111.222.333-44', 'ana.souza@exemplo.com',    '(11) 91234-5678'),
('Carlos Eduardo Lima', '222.333.444-55', 'carlos.lima@exemplo.com',  '(21) 92345-6789'),
('Fernanda Ribeiro',    '333.444.555-66', 'fernanda.ribeiro@exemplo.com', '(31) 93456-7890'),
('João Pedro Alves',    '444.555.666-77', 'joao.alves@exemplo.com',   '(41) 94567-8901'),
('Mariana Costa',       '555.666.777-88', 'mariana.costa@exemplo.com','(51) 95678-9012');

-- 2) Atendimentos TOPdesk
INSERT INTO dbo.AtendimentosTopdesk (ClienteId, NumeroChamado, Assunto, Descricao, Status, DataAbertura, DataFechamento) VALUES
(1, 'TOP-000123', 'Erro ao acessar sistema',        'Cliente relata mensagem de erro 500 ao tentar logar no portal.', 'Fechado',    '2026-06-01 09:15', '2026-06-02 14:30'),
(1, 'TOP-000145', 'Dúvida sobre fatura',            'Cliente questiona cobrança duplicada na fatura de junho.',        'Fechado',    '2026-06-10 11:00', '2026-06-10 16:45'),
(2, 'TOP-000198', 'Lentidão no sistema',            'Sistema apresentando lentidão excessiva durante geração de relatórios.', 'Em Andamento', '2026-07-05 08:20', NULL),
(3, 'TOP-000210', 'Solicitação de novo usuário',    'Cliente solicita criação de acesso para novo colaborador.',       'Fechado',    '2026-07-12 10:00', '2026-07-12 10:40'),
(4, 'TOP-000234', 'Falha na integração de API',     'Integração com sistema externo retornando timeout constante.',    'Em Andamento', '2026-07-20 13:10', NULL),
(5, 'TOP-000255', 'Reset de senha',                 'Cliente não consegue redefinir senha via portal de autoatendimento.', 'Fechado', '2026-07-25 15:30', '2026-07-25 15:50');

-- 3) Transcrições de ligações
INSERT INTO dbo.TranscricoesLigacoes (ClienteId, AtendimentoId, Transcricao, DataLigacao, DuracaoSegundos) VALUES
(1, 1, 'Atendente: Bom dia, em que posso ajudar? Cliente: Estou recebendo erro 500 ao tentar acessar o sistema desde ontem. Atendente: Vou verificar os logs e retorno em instantes.', '2026-06-01 09:16', 320),
(1, 2, 'Atendente: Sobre a fatura de junho, identificamos uma cobrança duplicada e já solicitamos o estorno. Cliente: Perfeito, obrigado pela agilidade.', '2026-06-10 11:05', 180),
(2, 3, 'Cliente: O sistema está muito lento para gerar relatórios, principalmente à tarde. Atendente: Vamos escalar para o time de infraestrutura para análise de performance.', '2026-07-05 08:25', 260),
(3, 4, 'Cliente: Preciso de acesso para um novo colaborador que começou essa semana. Atendente: Sem problemas, vou criar o usuário agora mesmo.', '2026-07-12 10:02', 150),
(4, 5, 'Cliente: Nossa integração está caindo com timeout toda hora. Atendente: Identificamos instabilidade no endpoint externo, já abrimos chamado com o fornecedor.', '2026-07-20 13:15', 410),
(5, 6, 'Cliente: Não consigo redefinir minha senha, o link de recuperação não chega no e-mail. Atendente: Vou reenviar manualmente e confirmar o e-mail cadastrado.', '2026-07-25 15:32', 140);

-- 4) Tabela consolidada (texto pronto para chunking/embeddings)
INSERT INTO dbo.TabelaConsolidada (ClienteId, Origem, OrigemId, Conteudo) VALUES
(1, 'Topdesk',      1, 'Chamado TOP-000123 - Erro ao acessar sistema: Cliente relata mensagem de erro 500 ao tentar logar no portal. Status: Fechado.'),
(1, 'Transcricao',  1, 'Ligação sobre chamado TOP-000123: Atendente verificou logs e resolveu o erro 500 de acesso ao sistema.'),
(1, 'Topdesk',      2, 'Chamado TOP-000145 - Dúvida sobre fatura: Cliente questiona cobrança duplicada na fatura de junho. Status: Fechado.'),
(2, 'Topdesk',      3, 'Chamado TOP-000198 - Lentidão no sistema: Sistema apresentando lentidão excessiva durante geração de relatórios. Status: Em Andamento.'),
(3, 'Topdesk',      4, 'Chamado TOP-000210 - Solicitação de novo usuário: Cliente solicita criação de acesso para novo colaborador. Status: Fechado.'),
(4, 'Topdesk',      5, 'Chamado TOP-000234 - Falha na integração de API: Integração com sistema externo retornando timeout constante. Status: Em Andamento.'),
(5, 'Topdesk',      6, 'Chamado TOP-000255 - Reset de senha: Cliente não consegue redefinir senha via portal de autoatendimento. Status: Fechado.');
