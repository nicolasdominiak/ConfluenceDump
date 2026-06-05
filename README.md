# confluence_space_dump.py

Script Python que varre **todas as páginas de um Space do Confluence Cloud**, converte o conteúdo de HTML para Markdown limpo e salva cada página como um arquivo `.md` no disco — sem depender de folders ou hierarquia.

---

## O que o script faz

```
Confluence API (Space inteiro) → HTML → limpeza de tags → Markdown → arquivo .md no disco
```

1. Autentica na API REST do Confluence usando e-mail + API Token
2. Lista **todas as páginas publicadas** do space via paginação automática (lotes de 100)
3. Busca o conteúdo HTML completo de cada página (tenta API v2, cai para v1 se necessário)
4. Converte o HTML para Markdown, tratando elementos específicos do Confluence
5. Salva cada página como `<titulo-slugificado>.md` no diretório configurado
6. Evita sobrescrever arquivos com o mesmo slug adicionando `_1`, `_2`, etc.

> **Diferença em relação ao `confluence_to_skills.py` original:**  
> O script original pegava apenas as páginas filhas diretas de um folder específico.  
> Este novo script ignora hierarquia e varre o space inteiro de uma vez.

---

## Estrutura de arquivos do projeto

```
confluence_dump/
├── confluence_space_dump.py   ← script principal
├── .env                       ← suas credenciais (NÃO versionar)
└── .env.example               ← modelo seguro para compartilhar
```

---

## Pré-requisitos

**Python 3.10+** instalado. Verificar com:

```bash
py -3 --version
```

Instalar as dependências:

```bash
py -3 -m pip install requests markdownify python-dotenv
```

| Pacote | Uso |
|---|---|
| `requests` | Chamadas à API REST do Confluence |
| `markdownify` | Conversão de HTML para Markdown |
| `python-dotenv` | Leitura das variáveis do arquivo `.env` |

---

## Configuração

### 1. Criar o arquivo `.env`

Crie um arquivo chamado `.env` na mesma pasta do script com as variáveis abaixo:

```env
CONFLUENCE_BASE_URL=https://suaempresa.atlassian.net
CONFLUENCE_EMAIL=seu@email.com
CONFLUENCE_API_TOKEN=<token gerado em id.atlassian.com>
CONFLUENCE_SPACE_KEY=MC
OUTPUT_DIR=~/Desktop/confluence_dump
```

### Descrição das variáveis

| Variável | Obrigatória | Descrição |
|---|---|---|
| `CONFLUENCE_BASE_URL` | Sim | URL base da instância Atlassian |
| `CONFLUENCE_EMAIL` | Sim | E-mail corporativo vinculado à conta Atlassian |
| `CONFLUENCE_API_TOKEN` | Sim | Token gerado em [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `CONFLUENCE_SPACE_KEY` | Sim | Chave do space (ex: `MC`, `OPS`, `ENG`) |
| `OUTPUT_DIR` | Não | Pasta de destino dos `.md` (padrão: `~/Desktop/confluence_dump`) |

### 2. Gerar o API Token

1. Acesse [id.atlassian.com → Security → API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Clique em **Create API Token**
3. Dê um nome (ex: `confluence-dump-script`)
4. Copie o token gerado e cole no `.env`

> ⚠️ **Segurança:** O arquivo `.env` contém credenciais reais. Nunca suba esse arquivo para Git ou compartilhe com outras pessoas. Adicione `.env` ao seu `.gitignore`.

---

## Como executar

Abra o terminal na pasta do projeto e rode:

```bash
py -3 confluence_space_dump.py
```

### Saída esperada no terminal

```
============================================================
Confluence Space Dump  →  Space: MC
============================================================

Buscando todas as páginas do space 'MC'...
  └─ Carregadas 150 páginas...
✓ 150 página(s) encontrada(s). Iniciando extração...

[   1/150] 20260105 - Jogue e Ganhe com crash em iOS     ✓
[   2/150] 20260220 - Home de Shopping não carrega       ✓
[   3/150] Runbook - Deploy pipeline                     ✓
...
[  150/150] Retrospectiva Q1 2026                        ✓

============================================================
Concluído!
  ✓ Salvas : 148
  ⚠ Vazias :   1
  ✗ Erros  :   1
  📁 Pasta  : C:\Users\seu_nome\Desktop\confluence_dump
============================================================
```

---

## Estrutura do código

### Funções principais

#### `get_all_pages(space_key)`
Retorna todas as páginas publicadas (`status: current`, `type: page`) do space usando paginação automática em lotes de 100. Inclui um delay de 100ms entre páginas para não ser bloqueado por rate-limit da API.

#### `get_page_content(page_id)`
Busca o corpo HTML da página em formato `storage` (HTML interno do Confluence). Tenta a API v2 primeiro; se falhar, usa a v1 como fallback.

#### `html_to_markdown(html)`
Converte o HTML do Confluence para Markdown limpo em quatro etapas:

| Etapa | O que faz |
|---|---|
| **1. Task-lists** | Converte `<ac:task>` em checkboxes Markdown `[ ]` / `[x]` |
| **2. Structured macros** | Remove tags de macro (`warning`, `note`, etc.) mas preserva o conteúdo interno de `<ac:rich-text-body>` |
| **3. ADF extensions** | Remove metadados de painéis ADF, preserva conteúdo de `<ac:adf-content>` |
| **4. Limpeza final** | Remove todas as demais tags `ac:` e `ri:` residuais |

Após a limpeza, chama `markdownify` para converter o HTML restante em Markdown padrão.

#### `slugify(text)`
Transforma o título da página em nome de arquivo seguro: remove caracteres especiais, converte para minúsculas, substitui espaços por `_`. Limita a 120 caracteres para evitar nomes gigantes.

#### `save_page(title, content)`
Salva o arquivo `.md` no diretório de saída. Se já existir um arquivo com o mesmo slug, adiciona sufixo `_1`, `_2`, etc., evitando sobrescritas acidentais.

#### `run()`
Ponto de entrada do script. Valida as variáveis de ambiente obrigatórias, busca todas as páginas e chama o pipeline de conversão para cada uma. Exibe um resumo ao final com contagem de sucesso, páginas vazias e erros.

---

## Comparativo com o script original

| Característica | `confluence_to_skills.py` (original) | `confluence_space_dump.py` (novo) |
|---|---|---|
| **Escopo** | Filhos diretos de um folder | Todas as páginas do space |
| **Configuração necessária** | `CONFLUENCE_FOLDER_ID` ou `CONFLUENCE_FOLDER` | Apenas `CONFLUENCE_SPACE_KEY` |
| **Sub-páginas** | Não incluídas | Incluídas automaticamente |
| **Hierarquia** | Respeitada | Ignorada — tudo plano na mesma pasta |
| **Proteção de nomes** | Sobrescreve arquivos com mesmo slug | Adiciona `_1`, `_2`... para evitar colisão |
| **Rate-limit** | Sem delay | Delay de 50-100ms entre requisições |
| **Tamanho do slug** | Sem limite | Máximo 120 caracteres |

---

## Limitações conhecidas

- **Imagens e anexos não são baixados** — apenas texto e links são preservados nos `.md`
- **Macros complexas** como *Jira Issues*, *Chart* e *Roadmap* são removidas sem conteúdo equivalente
- **Páginas de blog** do Confluence não são incluídas (apenas `type: page`)
- **Páginas arquivadas** (`status: archived`) são ignoradas por padrão — apenas páginas com `status: current` são extraídas
- A pasta de saída fica **plana** (sem subpastas por hierarquia). Para organizar por árvore de páginas, seria necessário adaptar o script para buscar os títulos dos ancestrais de cada página

---

## Solução de problemas

| Erro | Causa provável | Solução |
|---|---|---|
| `✗ Variáveis ausentes` | `.env` não criado ou mal configurado | Verifique o nome do arquivo e os valores |
| `401 Unauthorized` | Token inválido ou expirado | Gere um novo token em id.atlassian.com |
| `403 Forbidden` | Sem permissão no space | Solicite acesso ao administrador do Confluence |
| `404 Not Found` | `SPACE_KEY` incorreto | Verifique a chave do space na URL do Confluence |
| Arquivos com conteúdo vazio | Página existe mas não tem body | Normal — o script avisa com `⚠ vazia` e pula |
