import tkinter as tk
from tkinter import ttk
import psutil
import ctypes
import os
from PIL import Image, ImageTk
import win32api
import win32gui
import win32con
import tempfile
import atexit

# ---------------------------
# API do Windows
# ---------------------------
k32, p32 = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
PERM_QUERY, PERM_KILL = 0x0400 | 0x0010, 0x0001 | 0x00100000

# Limpa memória de um processo
limpar_ram = lambda pid: (h := k32.OpenProcess(PERM_QUERY, 0, pid)) and (p32.EmptyWorkingSet(h), k32.CloseHandle(h))[0]
matar_proc = lambda pid: (h := k32.OpenProcess(PERM_KILL, 0, pid)) and (k32.TerminateProcess(h, 1), k32.CloseHandle(h))[0]
limpar_cache = lambda: k32.SetSystemFileCacheSize(-1, -1, 0) if hasattr(k32, 'SetSystemFileCacheSize') else 0

# ---------------------------
# Ícones em cache
# ---------------------------
ícones, arqs_temp = {}, []

def obter_exe(pid):
    try: return psutil.Process(pid).exe()
    except: return None

def obter_ícone(caminho, tam=16):
    if not caminho or caminho in ícones: return ícones.get(caminho)
    try:
        ícone_grande, _ = win32gui.ExtractIconEx(caminho, 0, nIcons=1)
        if not ícone_grande: return None
        dc = win32gui.GetDC(0)
        hbmp = win32gui.CreateCompatibleBitmap(dc, tam, tam)
        dc_mem = win32gui.CreateCompatibleDC(dc)
        hbm_old = win32gui.SelectObject(dc_mem, hbmp)
        win32gui.FillRect(dc_mem, (0,0,tam,tam), win32gui.GetSysColorBrush(win32con.COLOR_WINDOW))
        win32gui.DrawIconEx(dc_mem, 0,0, ícone_grande[0], tam, tam, 0, None, win32con.DI_NORMAL)
        win32gui.SelectObject(dc_mem, hbm_old)
        win32gui.DeleteDC(dc_mem)
        win32gui.ReleaseDC(0, dc)
        win32gui.DestroyIcon(ícone_grande[0])
        dados = win32gui.GetBitmapBits(hbmp, True)
        img = Image.frombuffer('RGBA', (tam,tam), dados, 'raw', 'BGRA', 0, 1).transpose(Image.FLIP_TOP_BOTTOM)
        win32gui.DeleteObject(hbmp)
        temp_path = os.path.join(tempfile.gettempdir(), f"ico_{hash(caminho)}.bmp")
        img.save(temp_path)
        arqs_temp.append(temp_path)
        ícones[caminho] = temp_path
        return temp_path
    except: return None

atexit.register(lambda: [os.remove(f) for f in arqs_temp if os.path.exists(f)])

# ---------------------------
# Formatação de memória
# ---------------------------
formatar = lambda b: next(f"{b:.1f} {u}" for u in ['B','KB','MB','GB'] if b < 1024 or not (b:=b/1024))

# ---------------------------
# Aplicativo
# ---------------------------
class LimpaRAM:
    def __init__(self, janela):
        self.janela, self.ref_imgs = janela, []
        janela.title("🧹 Limpeza de RAM")
        janela.geometry("680x560")
        janela.resizable(0, 0)
        janela.configure(bg="#f0f0f0")

        # Frame inferior (status) - cor um pouco mais escura
        self.frame_status = tk.Frame(janela, bg="#e0e0e0", height=24)
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

        # Área rolável
        self.main_frame = tk.Frame(janela, bg="#f0f0f0")
        self.main_frame.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(self.main_frame, bg="#f0f0f0", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.frame_itens = tk.Frame(self.canvas, bg="#f0f0f0")

        self.canvas.create_window((0, 0), window=self.frame_itens, anchor="nw", width=640)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.frame_itens.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.frame_itens.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self.roldar))
        self.frame_itens.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        self.atualizar_processos()
        self.id_auto = None
        self.agendar_atualizacao()

    def roldar(self, evento): self.canvas.yview_scroll(int(-1 * (evento.delta / 120)), "units")

    def agendar_atualizacao(self):
        if self.id_auto: self.janela.after_cancel(self.id_auto)
        self.id_auto = self.janela.after(2000, self.atualizar_auto)

    def atualizar_auto(self):
        try: self.atualizar_processos(); self.agendar_atualizacao()
        except tk.TclError: pass

    def atualizar_processos(self):
        for w in self.frame_itens.winfo_children(): w.destroy()
        self.ref_imgs.clear()

        mem = psutil.virtual_memory()
        total, uso_pct = mem.total, mem.percent
        self.adicionar_item_sistema(
            f"📊 RAM em Uso: {uso_pct:.1f}%",
            f"{formatar(mem.used)} / {formatar(mem.total)}",
            "#0078d7",
            uso_pct / 100
        )

        ignorar_usuarios = {'LOCAL SERVICE', 'NETWORK SERVICE', 'SYSTEM'}
        ignorar_nomes = {'svchost.exe','wininit.exe','csrss.exe','services.exe','lsass.exe','winlogon.exe','spoolsv.exe','dllhost.exe'}
        ignorar_pids = {4}

        processos = [
            (p.info['name'], p.info['pid'], p.info['memory_info'].rss)
            for p in psutil.process_iter(['pid','name','memory_info','username','exe'], ad_value=None)
            if p.info['memory_info'] and p.info['memory_info'].rss > 0
            and p.info.get('username') not in ignorar_usuarios
            and p.info['name'].lower() not in ignorar_nomes
            and p.info['pid'] not in ignorar_pids
            and not (p.info['name'].lower() == 'explorer.exe' and p.info['exe'] and 'Windows\\Explorer' in p.info['exe'])
        ]

        for nome, pid, mem_uso in sorted(processos, key=lambda x: x[2], reverse=True)[:100]:
            self.adicionar_item_processo(nome, pid, mem_uso, total)

    def adicionar_item_sistema(self, nome, valor, cor, razão):
        f = tk.Frame(self.frame_itens, bg="white", bd=1, relief="flat", padx=6, pady=3)
        f.pack(fill="x", padx=3, pady=1)

        tf = tk.Frame(f, bg="white"); tf.pack(side="left", padx=4)
        tk.Label(tf, text=nome, font=("Segoe UI", 9, "bold"), bg="white", fg="#222", anchor="w").pack(anchor="w")  # 🔼 Fonte maior
        tk.Label(tf, text=valor, font=("Segoe UI", 8), bg="white", fg="#555").pack(anchor="w")

        bf = tk.Frame(f, bg="#e0e0e0", height=10, width=180)
        bf.pack_propagate(0); bf.pack(side="right", padx=6, pady=1)
        tk.Frame(bf, bg=cor, width=max(2, int(180 * razão)), height=10).pack(side="left")

        btn_frame = tk.Frame(f, bg="white"); btn_frame.pack(side="right", padx=4)
        tk.Button(btn_frame, text="🔄", font=("Segoe UI", 7, "bold"), bg="#5a5a5a", fg="white", relief="flat", width=2, command=self.atualizar_processos).pack(side="left")
        tk.Button(btn_frame, text="🧹", font=("Segoe UI", 7, "bold"), bg="#0078d7", fg="white", relief="flat", width=2, command=self.limpar_memoria).pack(side="left", padx=(3,0))

    def adicionar_item_processo(self, nome, pid, uso_mem, total_ram):
        f = tk.Frame(self.frame_itens, bg="white", bd=1, relief="flat", padx=6, pady=2)
        f.pack(fill="x", padx=3, pady=1)

        lbl_icone = tk.Label(f, bg="white", width=3); lbl_icone.pack(side="left", padx=3)
        exe = obter_exe(pid)
        if exe and (caminho_img := obter_ícone(exe)):
            try:
                img = ImageTk.PhotoImage(Image.open(caminho_img).resize((16,16), Image.Resampling.LANCZOS))
                lbl_icone.config(image=img); self.ref_imgs.append(img)
            except: lbl_icone.config(text="•", fg="#0078d7")
        else: lbl_icone.config(text="•", fg="#0078d7")

        tf = tk.Frame(f, bg="white"); tf.pack(side="left", padx=2)
        tk.Label(tf, text=nome, font=("Segoe UI", 8, "bold"), bg="white", fg="#333", anchor="w", wraplength=160).pack(anchor="w")  # 🔼 Fonte maior
        tk.Label(tf, text=formatar(uso_mem), font=("Segoe UI", 7), bg="white", fg="#666").pack(anchor="w")

        bf = tk.Frame(f, bg="#e0e0e0", height=8, width=160)
        bf.pack_propagate(0); bf.pack(side="right", padx=4)
        tk.Frame(bf, bg="#0078d7", width=max(1, int(160 * (uso_mem / total_ram))), height=8).pack(side="left")

        tk.Button(f, text="✕", font=("Segoe UI", 6, "bold"), bg="#d9534f", fg="white", relief="flat", width=2, command=lambda p=pid, n=nome: self.confirmar_matar(p, n)).pack(side="right", padx=1)

    def confirmar_matar(self, pid, nome):
        if tk.messagebox.askyesno("Encerrar", f"Encerrar:\n{nome} (PID: {pid})?\nPerda de dados possível."):
            matar_proc(pid); self.atualizar_processos()

    def limpar_memoria(self):
        antes = psutil.virtual_memory().used
        otimizados = sum(1 for p in psutil.process_iter(['pid'], ad_value=None) if limpar_ram(p.info['pid']))
        limpar_cache()
        depois = psutil.virtual_memory().used
        liberado = antes - depois
        total = psutil.virtual_memory().total
        pct = (liberado / total) * 100 if liberado > 0 else 0
        self.label_status.config(text=f"🧹 RAM limpa! +{formatar(liberado)} ({pct:.1f}%)")
        self.atualizar_processos()

# ---------------------------
# Execução
# ---------------------------
if __name__ == "__main__":
    if os.name != 'nt': print("Apenas para Windows."); exit()
    janela = tk.Tk()
    app = LimpaRAM(janela)
    janela.mainloop()
