-- ============================
-- Tabela de Usuários
-- ============================
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================
-- Tabela de Conversas
-- ============================
CREATE TABLE conversas (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    criado_por INT NOT NULL,
    CONSTRAINT fk_conversa_usuario FOREIGN KEY (criado_por)
        REFERENCES usuarios (id)
        ON DELETE CASCADE
);

-- Índice para buscar rápido conversas por criador
CREATE INDEX idx_conversas_criado_por ON conversas(criado_por);

-- ============================
-- Tabela de Mensagens
-- ============================
CREATE TABLE mensagens (
    id SERIAL PRIMARY KEY,
    conversa_id INT NOT NULL,
    usuario_id INT NOT NULL,
    conteudo TEXT NOT NULL,
    enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msg_conversa FOREIGN KEY (conversa_id)
        REFERENCES conversas (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_msg_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE CASCADE
);

-- Índices para performance
CREATE INDEX idx_mensagens_conversa ON mensagens(conversa_id);
CREATE INDEX idx_mensagens_usuario ON mensagens(usuario_id);

-- ============================
-- Tabela de Logs
-- ============================
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL,
    acao VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_log_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE CASCADE
);

-- Índice para auditoria rápida
CREATE INDEX idx_logs_usuario ON logs(usuario_id);
CREATE INDEX idx_logs_timestamp ON logs(timestamp);
