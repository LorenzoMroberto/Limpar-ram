import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import ctypes
import os

# Verifica sistema
if os.name != 'nt':
    print("Apenas para Windows.")
    exit()

# ---------------------------
# API do Windows
# ---------------------------
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
p32 = ctypes.WinDLL('psapi', use_last_error=True)

PERM_QUERY = 0x0400 | 0x0010  # PROCESS_QUERY_INFORMATION | VM_READ
PERM_KILL = 0x0001 | 0x00100000  # PROCESS_TERMINATE | QUERY_INFO

def limpar_ram(pid):
    h = k32.OpenProcess(PERM_QUERY, False, pid)
    if not h:
        return False
    p32.EmptyWorkingSet(h, 0)
    k32.CloseHandle(h)
    return True

def matar_processo(pid):
    h = k32.OpenProcess(PERM_KILL, False, pid)
    if not h:
        return False
    k32.TerminateProcess(h, 1)
    k32.CloseHandle(h)
    return True

def limpar_cache_sistema():
    if hasattr(k32, 'SetSystemFileCacheSize'):
        k32.SetSystemFileCacheSize(-1, -1, 0)

# ---------------------------
# Formatação
# ---------------------------
def formatar_bytes(b):
    for u in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

# ---------------------------
# Aplicativo
# ---------------------------
class LimpaRAM:
    def __init__(self, janela):
        self.janela = janela
        self.update_id = None
        self.configurar_janela()
        self.criar_interface()
        self.atualizar_processos()
        self.agendar_atualizacao()

    def configurar_janela(self):
        self.janela.title("🧹 Limpeza de RAM")
        self.janela.geometry("680x560")
        self.janela.resizable(False, False)
        self.janela.configure(bg="#f0f0f0")

    def criar_interface(self):
        # Status bar
        self.frame_status = tk.Frame(self.janela, bg="#e0e0e0", height=24)
        self.frame_status.pack(side="bottom", fill="x")
        self.frame_status.pack_propagate(False)
        self.label_status = tk.Label(
            self.frame_status,
            text="Pronto.",
            font=("Segoe UI", 8),
            bg="#e0e0e0",
            fg="#333",
            anchor="center"
        )
        self.label_status.pack(expand=True)

        # Container principal
        container = tk.Frame(self.janela, bg="#f0f0f0")
        container.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(container, bg="#f0f0f0", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.frame_itens = tk.Frame(self.canvas, bg="#f0f0f0")

        self.canvas_frame_window = self.canvas.create_window((0, 0), window=self.frame_itens, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.frame_itens.bind("<Configure>", self._ajustar_scroll)
        self.canvas.bind("<Configure>", self._ajustar_largura)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._roldar))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _ajustar_scroll(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _ajustar_largura(self, e):
        self.canvas.itemconfig(self.canvas_frame_window, width=e.width)

    def _roldar(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def agendar_atualizacao(self):
        if self.update_id:
            self.janela.after_cancel(self.update_id)
        self.update_id = self.janela.after(5000, self.atualizar_auto)

    def atualizar_auto(self):
        try:
            self.atualizar_processos()
            self.agendar_atualizacao()
        except tk.TclError:
            pass

    def atualizar_processos(self):
        for w in self.frame_itens.winfo_children():
            w.destroy()

        mem = psutil.virtual_memory()
        total_ram = mem.total
        uso_pct = mem.percent

        self.adicionar_item_sistema(
            f"📊 RAM em Uso: {uso_pct:.1f}%",
            f"{formatar_bytes(mem.used)} / {formatar_bytes(mem.total)}",
            "#0078d7",
            uso_pct / 100
        )

        # Filtros
        ignorar_usuarios = {'LOCAL SERVICE', 'NETWORK SERVICE', 'SYSTEM'}
        ignorar_nomes = {
            'svchost.exe', 'wininit.exe', 'csrss.exe', 'services.exe',
            'lsass.exe', 'winlogon.exe', 'spoolsv.exe', 'dllhost.exe'
        }
        ignorar_pids = {4}

        processos = []
        try:
            for p in psutil.process_iter(['pid', 'name', 'memory_info', 'username'], ad_value=None):
                info = p.info
                if not info['memory_info'] or info['memory_info'].rss <= 0:
                    continue
                if info.get('username') in ignorar_usuarios:
                    continue
                if info['name'].lower() in ignorar_nomes:
                    continue
                if info['pid'] in ignorar_pids:
                    continue
                if info['name'].lower() == 'explorer.exe' and 'Windows\\Explorer' in str(p.exe()).replace('/', '\\'):
                    continue
                processos.append((info['name'], info['pid'], info['memory_info'].rss))
        except:
            pass

        for nome, pid, uso_mem in sorted(processos, key=lambda x: x[2], reverse=True)[:100]:
            self.adicionar_item_processo(nome, pid, uso_mem, total_ram)

    def adicionar_item_sistema(self, nome, valor, cor, razao):
        f = tk.Frame(self.frame_itens, bg="white", bd=1, relief="flat", padx=6, pady=3)
        f.pack(fill="x", padx=3, pady=1)

        tf = tk.Frame(f, bg="white")
        tf.pack(side="left", fill="x", expand=True, padx=4)
        tk.Label(tf, text=nome, font=("Segoe UI", 9, "bold"), bg="white", fg="#222", anchor="w").pack(anchor="w")
        tk.Label(tf, text=valor, font=("Segoe UI", 8), bg="white", fg="#555").pack(anchor="w")

        # Barra de uso (tamanho real proporcional)
        bf = tk.Frame(f, bg="#e0e0e0", height=10, width=180)
        bf.pack_propagate(False)
        bf.pack(side="right", padx=6, pady=1)
        largura_barra = max(2, int(180 * razao))  # Largura real em pixels
        tk.Frame(bf, bg=cor, width=largura_barra, height=10).pack(side="left")

        btn_frame = tk.Frame(f, bg="white")
        btn_frame.pack(side="right", padx=4)
        tk.Button(btn_frame, text="🔄", font=("Segoe UI", 7, "bold"), bg="#5a5a5a", fg="white", relief="flat", width=2,
                  command=self.atualizar_processos).pack(side="left")
        tk.Button(btn_frame, text="🧹", font=("Segoe UI", 7, "bold"), bg="#0078d7", fg="white", relief="flat", width=2,
                  command=self.limpar_memoria).pack(side="left", padx=(3, 0))

    def adicionar_item_processo(self, nome, pid, uso_mem, total_ram):
        f = tk.Frame(self.frame_itens, bg="white", bd=1, relief="flat", padx=6, pady=2)
        f.pack(fill="x", padx=3, pady=1)

        # Ícone genérico
        tk.Label(f, text="●", font=("Segoe UI", 10), fg="#0078d7", bg="white").pack(side="left", padx=(3, 6))

        tf = tk.Frame(f, bg="white")
        tf.pack(side="left", fill="x", expand=True, padx=2)
        tk.Label(tf, text=nome, font=("Segoe UI", 8, "bold"), bg="white", fg="#333", anchor="w",
                 wraplength=200).pack(anchor="w")
        tk.Label(tf, text=formatar_bytes(uso_mem), font=("Segoe UI", 7), bg="white", fg="#666").pack(anchor="w")

        # Barra de uso proporcional (corrigida)
        bf = tk.Frame(f, bg="#e0e0e0", height=8, width=160)
        bf.pack_propagate(False)
        bf.pack(side="right", padx=4)
        largura_barra = max(1, int(160 * (uso_mem / total_ram)))  # Proporcional ao uso
        tk.Frame(bf, bg="#0078d7", width=largura_barra, height=8).pack(side="left")

        tk.Button(f, text="✕", font=("Segoe UI", 6, "bold"), bg="#d9534f", fg="white", relief="flat", width=2,
                  command=lambda p=pid, n=nome: self.confirmar_matar(p, n)).pack(side="right", padx=1)

    def confirmar_matar(self, pid, nome):
        if messagebox.askyesno("Encerrar", f"Encerrar:\n{nome} (PID: {pid})?\nPerda de dados possível."):
            matar_processo(pid)
            self.label_status.config(text=f"🛑 {nome} encerrado.")
            self.atualizar_processos()

    def limpar_memoria(self):
        antes = psutil.virtual_memory().used
        otimizados = 0
        for p in psutil.process_iter(['pid'], ad_value=None):
            try:
                if limpar_ram(p.info['pid']):
                    otimizados += 1
            except:
                continue
        limpar_cache_sistema()
        depois = psutil.virtual_memory().used
        liberado = antes - depois
        pct = (liberado / psutil.virtual_memory().total) * 100 if liberado > 0 else 0
        self.label_status.config(text=f"🧹 RAM limpa! +{formatar_bytes(liberado)} ({pct:.1f}%)")
        self.atualizar_processos()

# ---------------------------
# Execução
# ---------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = LimpaRAM(root)
    root.mainloop()
