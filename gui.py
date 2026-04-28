# gui.py
# Responsabilidade: interface gráfica completa da IA local.
# Usa apenas tkinter (já vem com Python — zero instalação).
# Roda em thread separada para não travar a UI durante respostas.

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import threading
import os

from model import gerar_resposta_stream
from memory import (nova_sessao, salvar_historico,
                    carregar_historico, listar_sessoes)
from summarizer import resumir_historico, deve_resumir
from config import obter, carregar_config
from tools import executar_tool
from trigger import detectar_e_executar


# ─── CORES E FONTES ───────────────────────────────────────────────────────────

CORES = {
    "fundo":         "#1e1e2e",   # fundo geral escuro
    "painel":        "#181825",   # painéis laterais
    "entrada":       "#313244",   # campo de texto
    "botao":         "#45475a",   # botões normais
    "botao_hover":   "#585b70",   # botões ao passar o mouse
    "botao_tool":    "#1e66f5",   # botões de tools (azul)
    "botao_nova":    "#40a02b",   # botão nova sessão (verde)
    "botao_enviar":  "#1e66f5",   # botão enviar
    "texto":         "#cdd6f4",   # texto principal
    "texto_fraco":   "#6c7086",   # texto secundário
    "usuario":       "#89b4fa",   # mensagens do usuário
    "ia":            "#a6e3a1",   # mensagens da IA
    "tool":          "#f9e2af",   # resultados de tools
    "sessao_ativa":  "#313244",   # sessão selecionada
    "borda":         "#45475a",   # bordas
}

FONTES = {
    "chat":    ("Consolas", 11),
    "input":   ("Consolas", 11),
    "titulo":  ("Segoe UI", 13, "bold"),
    "botao":   ("Segoe UI", 10),
    "sessao":  ("Consolas", 9),
    "label":   ("Segoe UI", 10, "bold"),
}


# ─── JANELA PRINCIPAL ─────────────────────────────────────────────────────────

class AppIA(tk.Tk):
    def __init__(self):
        super().__init__()

        self.config_dados = carregar_config()
        self.nome = self.config_dados["nome_assistente"]

        self.title(f"🤖 {self.nome} — IA Local")
        self.geometry("1000x680")
        self.minsize(800, 500)
        self.configure(bg=CORES["fundo"])

        # Estado da sessão atual
        self.arquivo_sessao: str = nova_sessao()
        self.historico: list[dict] = [self._system_prompt()]
        self.respondendo: bool = False   # lock para evitar envios duplos

        self._construir_ui()
        self._atualizar_lista_sessoes()

        # Mensagem de boas-vindas
        self._exibir_mensagem(
            "sistema",
            f"🤖 {self.nome} iniciada. Como posso ajudar?"
        )

    def _system_prompt(self) -> dict:
        return {"role": "system", "content": obter("persona")}

    # ─── CONSTRUÇÃO DA UI ─────────────────────────────────────────────────────

    def _construir_ui(self):
        """Monta todos os widgets da interface."""
        self._barra_superior()

        # Container principal (painel esquerdo + chat)
        main = tk.Frame(self, bg=CORES["fundo"])
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._painel_esquerdo(main)
        self._area_chat(main)

    def _barra_superior(self):
        """Barra do topo com nome da IA e modelo."""
        barra = tk.Frame(self, bg=CORES["painel"], height=48)
        barra.pack(fill="x", padx=8, pady=8)
        barra.pack_propagate(False)

        tk.Label(
            barra,
            text=f"🤖  {self.nome}",
            font=FONTES["titulo"],
            bg=CORES["painel"],
            fg=CORES["texto"]
        ).pack(side="left", padx=16, pady=8)

        modelo = self.config_dados.get("modelo", "llama3")
        tk.Label(
            barra,
            text=f"modelo: {modelo}",
            font=("Segoe UI", 9),
            bg=CORES["painel"],
            fg=CORES["texto_fraco"]
        ).pack(side="right", padx=16)

    def _painel_esquerdo(self, pai):
        """Painel esquerdo com lista de sessões e botões de tools."""
        painel = tk.Frame(pai, bg=CORES["painel"], width=200)
        painel.pack(side="left", fill="y", padx=(0, 8))
        painel.pack_propagate(False)

        # ── Sessões ───────────────────────────────────────────────────────────
        tk.Label(
            painel,
            text="📂  Sessões",
            font=FONTES["label"],
            bg=CORES["painel"],
            fg=CORES["texto"]
        ).pack(anchor="w", padx=12, pady=(12, 4))

        # Frame com scroll para lista de sessões
        frame_lista = tk.Frame(painel, bg=CORES["painel"])
        frame_lista.pack(fill="both", expand=True, padx=8)

        scroll = tk.Scrollbar(frame_lista, bg=CORES["painel"])
        scroll.pack(side="right", fill="y")

        self.lista_sessoes = tk.Listbox(
            frame_lista,
            bg=CORES["entrada"],
            fg=CORES["texto"],
            selectbackground=CORES["sessao_ativa"],
            selectforeground=CORES["usuario"],
            font=FONTES["sessao"],
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scroll.set,
            cursor="hand2"
        )
        self.lista_sessoes.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.lista_sessoes.yview)
        self.lista_sessoes.bind("<<ListboxSelect>>", self._carregar_sessao)

        # Botão nova sessão
        self._botao(
            painel,
            "＋  Nova Sessão",
            self._nova_sessao,
            cor=CORES["botao_nova"]
        ).pack(fill="x", padx=8, pady=(4, 12))

        # ── Tools ─────────────────────────────────────────────────────────────
        tk.Label(
            painel,
            text="🛠️  Tools",
            font=FONTES["label"],
            bg=CORES["painel"],
            fg=CORES["texto"]
        ).pack(anchor="w", padx=12, pady=(4, 4))

        tools_config = [
            ("🕐  /hora",         "/hora",    ""),
            ("🌤️  /clima",        "/clima",   "cidade"),
            ("🧮  /calc",         "/calc",    "expressão"),
            ("📄  /ler arquivo",  "/ler",     None),   # None = abre file dialog
        ]

        for label, comando, placeholder in tools_config:
            self._botao_tool(painel, label, comando, placeholder)

    def _botao_tool(self, pai, label: str, comando: str, placeholder):
        """Cria botão de tool com comportamento específico."""
        def ao_clicar():
            if placeholder is None:
                # Abre seletor de arquivo
                caminho = filedialog.askopenfilename(
                    title="Selecionar arquivo",
                    filetypes=[("Arquivos de texto", "*.txt")]
                )
                if caminho:
                    self._executar_tool_gui(f"/ler {caminho}")
            elif placeholder:
                # Abre mini-janela de input
                self._mini_input(label, comando, placeholder)
            else:
                # Executa direto sem args
                self._executar_tool_gui(comando)

        self._botao(pai, label, ao_clicar, cor=CORES["botao_tool"]).pack(
            fill="x", padx=8, pady=2
        )

    def _area_chat(self, pai):
        """Área principal de chat com histórico e campo de input."""
        frame = tk.Frame(pai, bg=CORES["fundo"])
        frame.pack(side="left", fill="both", expand=True)

        # ── Histórico de mensagens ─────────────────────────────────────────
        self.area_texto = scrolledtext.ScrolledText(
            frame,
            bg=CORES["fundo"],
            fg=CORES["texto"],
            font=FONTES["chat"],
            wrap=tk.WORD,
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=8,
        )
        self.area_texto.pack(fill="both", expand=True)

        # Tags de cor por tipo de mensagem
        self.area_texto.tag_config("usuario", foreground=CORES["usuario"])
        self.area_texto.tag_config("ia",      foreground=CORES["ia"])
        self.area_texto.tag_config("tool",    foreground=CORES["tool"])
        self.area_texto.tag_config("sistema", foreground=CORES["texto_fraco"])
        self.area_texto.tag_config("erro",    foreground="#f38ba8")

        # ── Campo de input ─────────────────────────────────────────────────
        frame_input = tk.Frame(frame, bg=CORES["painel"], pady=8)
        frame_input.pack(fill="x")

        self.campo_input = tk.Text(
            frame_input,
            bg=CORES["entrada"],
            fg=CORES["texto"],
            font=FONTES["input"],
            height=2,
            wrap=tk.WORD,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=CORES["borda"],
            highlightcolor=CORES["usuario"],
            padx=8,
            pady=6,
            insertbackground=CORES["texto"],   # cor do cursor
        )
        self.campo_input.pack(side="left", fill="x", expand=True, padx=(8, 4))

        # Enter envia, Shift+Enter quebra linha
        self.campo_input.bind("<Return>",       self._ao_pressionar_enter)
        self.campo_input.bind("<Shift-Return>", lambda e: None)

        self._botao(
            frame_input,
            "  ➤  ",
            self._enviar,
            cor=CORES["botao_enviar"]
        ).pack(side="right", padx=(0, 8), ipady=6)

    # ─── HELPERS DE WIDGET ────────────────────────────────────────────────────

    def _botao(self, pai, texto, comando, cor=None):
        """Cria botão estilizado com efeito hover."""
        cor = cor or CORES["botao"]
        btn = tk.Button(
            pai,
            text=texto,
            command=comando,
            bg=cor,
            fg=CORES["texto"],
            font=FONTES["botao"],
            relief="flat",
            cursor="hand2",
            activebackground=CORES["botao_hover"],
            activeforeground=CORES["texto"],
            borderwidth=0,
            padx=8,
            pady=4,
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=CORES["botao_hover"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=cor))
        return btn

    def _mini_input(self, titulo: str, comando: str, placeholder: str):
        """Janela popup para inserir argumento de uma tool."""
        popup = tk.Toplevel(self)
        popup.title(titulo)
        popup.geometry("360x120")
        popup.resizable(False, False)
        popup.configure(bg=CORES["fundo"])
        popup.grab_set()   # modal

        tk.Label(
            popup,
            text=f"Informe {placeholder}:",
            font=FONTES["botao"],
            bg=CORES["fundo"],
            fg=CORES["texto"]
        ).pack(padx=16, pady=(16, 4), anchor="w")

        entrada = tk.Entry(
            popup,
            bg=CORES["entrada"],
            fg=CORES["texto"],
            font=FONTES["input"],
            insertbackground=CORES["texto"],
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=CORES["borda"],
        )
        entrada.pack(fill="x", padx=16)
        entrada.focus()

        def confirmar(event=None):
            valor = entrada.get().strip()
            popup.destroy()
            if valor:
                self._executar_tool_gui(f"{comando} {valor}")

        entrada.bind("<Return>", confirmar)
        self._botao(popup, "Executar", confirmar, cor=CORES["botao_tool"]).pack(
            pady=8
        )

    # ─── EXIBIÇÃO DE MENSAGENS ────────────────────────────────────────────────

    def _exibir_mensagem(self, tipo: str, texto: str):
        """
        Adiciona uma mensagem formatada na área de chat.

        Args:
            tipo: "usuario", "ia", "tool", "sistema", "erro"
            texto: conteúdo da mensagem
        """
        prefixos = {
            "usuario": f"\nVocê:  ",
            "ia":      f"\n{self.nome}:  ",
            "tool":    "\n🔍  ",
            "sistema": "\n",
            "erro":    "\n❌  ",
        }
        prefixo = prefixos.get(tipo, "\n")

        self.area_texto.config(state="normal")
        self.area_texto.insert("end", prefixo, tipo)
        self.area_texto.insert("end", texto + "\n", tipo)
        self.area_texto.config(state="disabled")
        self.area_texto.see("end")

    def _inserir_token(self, token: str):
        """Insere um token de streaming diretamente na área de chat."""
        self.area_texto.config(state="normal")
        self.area_texto.insert("end", token, "ia")
        self.area_texto.config(state="disabled")
        self.area_texto.see("end")

    def _iniciar_linha_ia(self):
        """Abre a linha da IA antes do streaming começar."""
        self.area_texto.config(state="normal")
        self.area_texto.insert("end", f"\n{self.nome}:  ", "ia")
        self.area_texto.config(state="disabled")

    # ─── LÓGICA DE ENVIO ──────────────────────────────────────────────────────

    def _ao_pressionar_enter(self, event):
        """Captura Enter (sem Shift) para enviar mensagem."""
        self._enviar()
        return "break"   # impede quebra de linha padrão

    def _enviar(self):
        """Lê o input, exibe e dispara a geração em thread separada."""
        if self.respondendo:
            return   # ignora envio duplo enquanto IA responde

        texto = self.campo_input.get("1.0", "end").strip()
        if not texto:
            return

        self.campo_input.delete("1.0", "end")
        self._exibir_mensagem("usuario", texto)
        self.respondendo = True

        # Roda em thread para não travar a UI
        threading.Thread(
            target=self._processar_mensagem,
            args=(texto,),
            daemon=True
        ).start()

    def _processar_mensagem(self, entrada: str):
        """
        Processa a mensagem em background:
        1. Verifica trigger automático
        2. Injeta contexto se houver tool
        3. Gera resposta com streaming
        4. Salva histórico
        """
        try:
            self.historico.append({"role": "user", "content": entrada})

            # Resumo automático se necessário
            if deve_resumir(self.historico):
                self.after(0, lambda: self._exibir_mensagem(
                    "sistema", "⚠️ Comprimindo histórico longo..."
                ))
                self.historico = resumir_historico(
                    self.historico, self.arquivo_sessao
                )

            # Trigger automático de tools
            encontrou, tool_usada, resultado_tool = detectar_e_executar(entrada)
            if encontrou:
                self.after(0, lambda: self._exibir_mensagem(
                    "tool", f"[{tool_usada}]\n{resultado_tool}"
                ))
                self.historico.append({
                    "role": "user",
                    "content": (
                        f"[Dado obtido via {tool_usada}]\n"
                        f"{resultado_tool}\n\n"
                        f"Use esses dados para responder: {entrada}"
                    )
                })

            # Inicia linha da IA e faz streaming
            self.after(0, self._iniciar_linha_ia)

            resposta_completa = ""
            for token in gerar_resposta_stream(self.historico):
                self.after(0, lambda t=token: self._inserir_token(t))
                resposta_completa += token

            # Quebra de linha após resposta
            self.after(0, lambda: self._inserir_token("\n"))

            # Salva no histórico
            self.historico.append({
                "role": "assistant",
                "content": resposta_completa
            })
            salvar_historico(self.arquivo_sessao, self.historico)

            # Atualiza lista de sessões na sidebar
            self.after(0, self._atualizar_lista_sessoes)

        except Exception as e:
            self.after(0, lambda: self._exibir_mensagem("erro", str(e)))

        finally:
            self.respondendo = False

    def _executar_tool_gui(self, comando: str):
        """Executa uma tool manualmente (via botão) e exibe resultado."""
        eh_tool, resultado = executar_tool(comando)
        if eh_tool:
            self._exibir_mensagem("tool", f"[{comando}]\n{resultado}")
            self.historico.append({
                "role": "user",
                "content": f"[Resultado de '{comando}']\n{resultado}"
            })
            self.respondendo = True
            threading.Thread(
                target=self._gerar_comentario_tool,
                args=(comando, resultado),
                daemon=True
            ).start()

    def _gerar_comentario_tool(self, comando: str, resultado: str):
        """A IA comenta o resultado da tool com streaming."""
        try:
            historico_temp = self.historico + [{
                "role": "user",
                "content": f"Comente brevemente o resultado: {resultado}"
            }]
            self.after(0, self._iniciar_linha_ia)
            resposta = ""
            for token in gerar_resposta_stream(historico_temp):
                self.after(0, lambda t=token: self._inserir_token(t))
                resposta += token
            self.after(0, lambda: self._inserir_token("\n"))
            self.historico.append({"role": "assistant", "content": resposta})
            salvar_historico(self.arquivo_sessao, self.historico)
        except Exception as e:
            self.after(0, lambda: self._exibir_mensagem("erro", str(e)))
        finally:
            self.respondendo = False

    # ─── GERENCIAMENTO DE SESSÕES ─────────────────────────────────────────────

    def _nova_sessao(self):
        """Inicia uma sessão completamente nova."""
        self.arquivo_sessao = nova_sessao()
        self.historico = [self._system_prompt()]

        self.area_texto.config(state="normal")
        self.area_texto.delete("1.0", "end")
        self.area_texto.config(state="disabled")

        self._exibir_mensagem("sistema", "🆕 Nova sessão iniciada.")
        self._atualizar_lista_sessoes()

    def _atualizar_lista_sessoes(self):
        """Recarrega a lista de sessões salvas na sidebar."""
        self.lista_sessoes.delete(0, "end")
        for caminho in listar_sessoes():
            # Mostra só o nome do arquivo, não o caminho completo
            nome = os.path.basename(caminho).replace(".json", "")
            self.lista_sessoes.insert("end", nome)

    def _carregar_sessao(self, event):
        """Carrega sessão selecionada na lista."""
        sel = self.lista_sessoes.curselection()
        if not sel:
            return

        idx = sel[0]
        sessoes = listar_sessoes()
        if idx >= len(sessoes):
            return

        caminho = sessoes[idx]
        historico = carregar_historico(caminho)

        if not historico:
            return

        self.arquivo_sessao = caminho
        self.historico = historico

        # Limpa e reconstrói o chat com o histórico carregado
        self.area_texto.config(state="normal")
        self.area_texto.delete("1.0", "end")
        self.area_texto.config(state="disabled")

        self._exibir_mensagem("sistema", f"📂 Sessão carregada: {os.path.basename(caminho)}")

        for msg in historico:
            if msg["role"] == "user" and not msg["content"].startswith("["):
                self._exibir_mensagem("usuario", msg["content"])
            elif msg["role"] == "assistant":
                self._exibir_mensagem("ia", msg["content"])


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AppIA()
    app.mainloop()
