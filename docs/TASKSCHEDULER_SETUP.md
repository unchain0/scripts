# Como Configurar o Script no Agendador de Tarefas do Windows

Este guia mostra como configurar o arquivo `run_selection.vbs` para executar automaticamente usando o Agendador de Tarefas (Task Scheduler) do Windows.

## O que o Script Faz

O arquivo `run_selection.vbs` executa o script Python `selection_process.py` usando o gerenciador de pacotes `uv`, de forma silenciosa (sem abrir janela de terminal).

## Pré-requisitos

- ✅ Windows com Agendador de Tarefas (Task Scheduler)
- ✅ Script `run_selection.vbs` e `selection_process.py` no mesmo diretório
- ✅ Python e `uv` package manager instalados e configurados no PATH

## Passo a Passo

### 1. Abrir o Agendador de Tarefas

**Opção A - Pesquisa:**

- Pressione `Win + S`
- Digite "Agendador de Tarefas" ou "Task Scheduler"
- Clique no aplicativo

**Opção B - Comando Executar:**

- Pressione `Win + R`
- Digite `taskschd.msc`
- Pressione Enter

### 2. Criar Nova Tarefa

1. No painel direito, clique em **"Criar Tarefa..."** (não "Criar Tarefa Básica")
2. Uma janela com abas será aberta

### 3. Aba "Geral"

Configure as seguintes opções:

- **Nome:** `Selection Process Automation` (ou outro nome de sua preferência)
- **Descrição:** `Executa o script de seleção automaticamente`
- **Opções de segurança:**
  - ☑️ Marque "Executar estando o usuário conectado ou não"
  - ☑️ Marque "Executar com privilégios mais altos" (se necessário)
  - ☑️ Marque "Oculto" (para não exibir janelas)
- **Configurar para:** Selecione sua versão do Windows

### 4. Aba "Disparadores" (Triggers)

Clique em **"Novo..."** para definir quando o script será executado:

#### Opções comuns

**Execução Diária:**

- **Iniciar a tarefa:** Em uma agenda
- **Configurações:** Diariamente
- **Hora:** Defina o horário desejado (ex: `09:00:00`)
- **Repetir a cada:** 1 dia

**Execução ao Iniciar o Sistema:**

- **Iniciar a tarefa:** Ao iniciar
- Configure atrasos se necessário

**Execução ao Fazer Login:**

- **Iniciar a tarefa:** Ao fazer logon
- **Qualquer usuário** ou **Usuário específico**

**Execução Personalizada:**

- Configure intervalos específicos conforme sua necessidade
- ☑️ Marque "Habilitado" antes de clicar em OK

### 5. Aba "Ações"

Clique em **"Novo..."** para definir o que será executado:

1. **Ação:** Iniciar um programa
2. **Programa/script:**

   ```bash
   wscript.exe
   ```

3. **Adicionar argumentos (opcional):**

   ```txt
   "d:\Workspace\scripts\run_selection.vbs"
   ```

   ⚠️ **IMPORTANTE:** Substitua pelo caminho completo do seu arquivo VBS (use aspas se o caminho tiver espaços)

4. **Iniciar em (opcional):**

   ```txt
   d:\Workspace\scripts
   ```

   ⚠️ **IMPORTANTE:** Use o diretório onde os scripts estão localizados

5. Clique em **OK**

### 6. Aba "Condições"

Configure conforme necessário:

- **Energia:**
  - ☐ Desmarque "Iniciar a tarefa apenas se o computador estiver conectado à energia CA" (se quiser executar em notebooks)
  
- **Rede:**
  - Configure se o script precisa de conexão de rede

### 7. Aba "Configurações"

Recomendações:

- ☑️ Marque "Permitir que a tarefa seja executada por demanda"
- ☑️ Marque "Executar tarefa assim que possível após perder um início agendado"
- ☐ Desmarque "Interromper a tarefa se ela estiver em execução por mais de:" (se o script puder demorar)
- **Se a tarefa já estiver em execução:** Selecione "Não iniciar uma nova instância"

### 8. Finalizar

Clique em **OK** para salvar a tarefa.

Se solicitado, insira a senha do usuário do Windows para confirmar.

## Testar a Configuração

### Executar Manualmente

1. No Agendador de Tarefas, localize sua tarefa na lista
2. Clique com o botão direito na tarefa
3. Selecione **"Executar"**
4. Verifique se o script foi executado corretamente

### Verificar Status

1. Na lista de tarefas, verifique a coluna **"Última Execução"**
2. Verifique a coluna **"Resultado da Última Execução"**
   - `0x0` = Sucesso
   - Outros códigos = Erro (clique duas vezes na tarefa para ver detalhes)

### Ver Histórico

1. Clique com o botão direito na tarefa
2. Selecione **"Propriedades"**
3. Vá para a aba **"Histórico"**
4. Analise os eventos de execução

## Solução de Problemas

### A tarefa não executa

- ✅ Verifique se o caminho do arquivo VBS está correto
- ✅ Confirme que `uv` está instalado e no PATH do sistema

   ```bash
   uv --version
   ```

- ✅ Teste o arquivo VBS manualmente (clique duas vezes nele)
- ✅ Verifique se o usuário tem permissões para executar o script
- ✅ Revise os logs no histórico da tarefa

### A tarefa executa mas dá erro

- ✅ Verifique o campo "Iniciar em" na aba Ações
- ✅ Certifique-se de que todas as dependências Python estão instaladas
- ✅ Execute o comando manualmente no terminal: `uv run selection_process.py`
- ✅ Verifique os logs do script (se houver)

### A janela do terminal aparece

- ✅ Certifique-se de estar usando `wscript.exe` e não `cscript.exe`
- ✅ Marque a opção "Oculto" na aba "Geral"
- ✅ Verifique se o arquivo VBS está correto (parâmetro `0` na linha 4)

## Comandos Úteis

### Executar tarefa via PowerShell

```powershell
Start-ScheduledTask -TaskName "Selection Process Automation"
```

### Desabilitar tarefa via PowerShell

```powershell
Disable-ScheduledTask -TaskName "Selection Process Automation"
```

### Habilitar tarefa via PowerShell

```powershell
Enable-ScheduledTask -TaskName "Selection Process Automation"
```

### Verificar status via PowerShell

```powershell
Get-ScheduledTask -TaskName "Selection Process Automation" | Get-ScheduledTaskInfo
```

## Modificar a Tarefa

Para modificar a configuração:

1. Abra o Agendador de Tarefas
2. Localize a tarefa na lista
3. Clique com o botão direito
4. Selecione **"Propriedades"**
5. Modifique as configurações necessárias
6. Clique em **OK** para salvar

## Remover a Tarefa

Para remover completamente:

1. Abra o Agendador de Tarefas
2. Localize a tarefa na lista
3. Clique com o botão direito
4. Selecione **"Excluir"**
5. Confirme a exclusão
