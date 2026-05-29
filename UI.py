import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os
import subprocess
from simulacion import SimulacionGuardiaOdontologica


# ── Paleta ─────────────────────────────────────────────────────────────────
BG_DARK  = "#0f1117"
BG_PANEL = "#1a1d27"
BG_CARD  = "#20243a"
ACCENT   = "#4fc3f7"
ACCENT2  = "#81d4fa"
GREEN    = "#69f0ae"
YELLOW   = "#ffd740"
RED      = "#ff5252"
PURPLE   = "#ce93d8"
FG_MAIN  = "#e8eaf6"
FG_DIM   = "#7986cb"
BORDER   = "#2a3050"
ROW_ODD  = "#1e2236"
ROW_EVEN = "#181b2c"
ROW_SEL  = "#1a3a5c"
ROW_LAST = "#2a1e00"

# Colores del header de grupos (organizador) — alineados al PDF
GRP_ITER    = "#1a1a2e"
GRP_LLEGADA = "#1a4d3a"   # verde agua
GRP_TRIAGE  = "#3d1a50"   # rosa/lila
GRP_ESPER_OD= "#1a3d1a"   # verde medio
GRP_ESPER_CI= "#0d2b50"   # azul medio
GRP_OD      = "#1e3d1e"   # verde claro
GRP_UNIFORME= "#1a2a4a"   # azul claro
GRP_ESTERIL = "#3d2010"   # salmon
GRP_DERIV   = "#2a1a40"   # lila
GRP_RETIRO  = "#3a1a1a"   # rojo oscuro
GRP_PERM    = "#1a2d3a"   # azul OBJETOS PERMANENTES
GRP_STAT    = "#252520"   # oscuro ESTADISTICAS
GRP_TEMP    = "#0d3d30"   # verde menta OBJETOS TEMPORALES
TXT_GRP     = "#d0e4f0"


class AppSimulacion:

    def __init__(self, root):
        self.root = root
        self.root.title("SIMULACIÓN 4K2 - 2026  |  Guardia Odontológica Sonrisas")
        self.root.configure(bg=BG_DARK)
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.geometry("1400x900")

        self._sim             = None
        self._df_full         = None
        self._df_filter       = None
        self._params_snapshot = {}
        self._ultima_iid      = None   # item id de la ultima fila en el tree

        self._col_polling = False
        self._build_styles()
        self._crear_widgets()

    # ── Estilos ───────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=BG_DARK, foreground=FG_MAIN,
                    fieldbackground=BG_CARD, troughcolor=BG_PANEL,
                    bordercolor=BORDER, darkcolor=BG_PANEL,
                    lightcolor=BG_PANEL, insertcolor=ACCENT)
        s.configure("TFrame",       background=BG_DARK)
        s.configure("TLabel",       background=BG_DARK, foreground=FG_MAIN)
        s.configure("Title.TLabel", background=BG_DARK, foreground=ACCENT,
                    font=("Consolas", 12, "bold"))
        s.configure("TEntry",       fieldbackground=BG_CARD, foreground=FG_MAIN,
                    insertcolor=ACCENT, bordercolor=BORDER, relief="flat")

        for name, bg, fg in [
            ("Run.TButton",    "#1e3a5f", ACCENT),
            ("Export.TButton", "#1a3a28", GREEN),
            ("Stats.TButton",  "#3a1a3a", PURPLE),
        ]:
            s.configure(name, background=bg, foreground=fg,
                        font=("Consolas", 9, "bold"),
                        borderwidth=0, relief="flat", padding=(10, 6))
            s.map(name,
                  background=[("active", ACCENT), ("pressed", ACCENT)],
                  foreground=[("active", BG_DARK), ("pressed", BG_DARK)])

        s.configure("Treeview",
                    background=ROW_ODD, fieldbackground=ROW_ODD,
                    foreground=FG_MAIN, rowheight=22,
                    font=("Consolas", 8), borderwidth=0)
        s.configure("Treeview.Heading",
                    background=BG_CARD, foreground=ACCENT2,
                    font=("Consolas", 8, "bold"),
                    borderwidth=0, relief="flat")
        s.map("Treeview",
              background=[("selected", ROW_SEL)],
              foreground=[("selected", FG_MAIN)])
        s.configure("TScrollbar",
                    background=BG_PANEL, troughcolor=BG_DARK,
                    bordercolor=BORDER, arrowcolor=FG_DIM)

    # ── Widgets principales ───────────────────────────────────────────────
    def _crear_widgets(self):
        header = tk.Frame(self.root, bg=BG_PANEL, height=46)
        header.pack(fill="x", side="top")
        tk.Label(header, text="SIMULACIÓN 4K2 - 2026",
                 bg=BG_PANEL, fg=ACCENT,
                 font=("Consolas", 13, "bold")).pack(side="left", padx=(18, 6), pady=10)
        tk.Label(header, text="|",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=("Consolas", 13)).pack(side="left", padx=4, pady=10)
        tk.Label(header, text="Guardia Odontológica Sonrisas",
                 bg=BG_PANEL, fg=FG_MAIN,
                 font=("Consolas", 13)).pack(side="left", padx=(4, 18), pady=10)

        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=8, pady=6)

        left = tk.Frame(main, bg=BG_DARK, width=340)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        # ── Status bar: entre el header y los parametros ─────────────────
        self._lbl_status = tk.Label(
            left,
            text="Ingrese los parámetros y presione SIMULAR.",
            bg="#111827", fg="#39ff14",
            font=("Consolas", 9, "bold"),
            wraplength=320, justify="left",
            anchor="w", pady=6, padx=10
        )
        self._lbl_status.pack(fill="x", side="top")
        self.root.after(300, lambda: self._menu_copia_label(self._lbl_status))
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", side="top")

        self._build_params(left)
        self._build_table_area(right)

    # ── Panel de parametros ───────────────────────────────────────────────
    def _build_params(self, parent):
        canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG_DARK)
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(wid, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

        self._entries = {}

        def section(title):
            tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(10, 2))
            ttk.Label(inner, text="  " + title,
                      style="Title.TLabel").pack(fill="x", pady=(0, 4))

        def param(label, key, default, hint=""):
            row = tk.Frame(inner, bg=BG_DARK)
            row.pack(fill="x", pady=2, padx=6)
            # Etiqueta con ancho fijo
            tk.Label(row, text=label, bg=BG_DARK, fg=FG_MAIN,
                     font=("Consolas", 9), width=26, anchor="w").pack(side="left")
            # Separador invisible para desplazar campo a la derecha
            tk.Frame(row, bg=BG_DARK, width=6).pack(side="left")
            e = tk.Entry(row, width=7, bg=BG_CARD, fg=ACCENT,
                         insertbackground=ACCENT, relief="flat",
                         font=("Consolas", 9), bd=0,
                         highlightbackground=BORDER, highlightthickness=1)
            e.insert(0, str(default))
            e.pack(side="left", padx=2)
            if hint:
                tk.Label(row, text=hint, bg=BG_DARK, fg=FG_DIM,
                         font=("Consolas", 8)).pack(side="left", padx=2)
            self._entries[key] = e

        section("SISTEMA")
        param("Media llegada (min)",          "media_llegada",         30, "exp-")
        param("Tiempo triage (min)",          "tiempo_triage",          5)
        param("Media Odontólogo (min)",       "media_odontologo",      30, "exp-")
        param("Uniforme A (min)",             "uniforme_a",            40, "unif")
        param("Uniforme B (min)",             "uniforme_b",            60, "unif")
        param("Tiempo paciencia (min)",       "tiempo_paciencia",      30)
        param("Frec. Esteriliz. (pac.)", "pacientes_esterilizar",  3)
        param("Tiempo esterilizac. (min)",    "tiempo_esterilizacion", 15)

        section("SIMULACION")
        param("Tiempo máximo (min)",   "tiempo_max",       480)
        param("Max. iteraciones (N)",  "max_iteraciones", 100000)

        section("VECTOR DE ESTADO")
        param("Inicio muestra j (hora)", "inicio_mostrar",   0)
        param("Cant. iteraciones i",     "cant_mostrar",   100)

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=10)

        ttk.Button(inner, text="SIMULAR",
                   style="Run.TButton",
                   command=self._run).pack(fill="x", padx=6, pady=3)
        ttk.Button(inner, text="ESTADÍSTICAS FINALES",
                   style="Stats.TButton",
                   command=self._ver_estadisticas).pack(fill="x", padx=6, pady=3)
        ttk.Button(inner, text="EXPORTAR A EXCEL",
                   style="Export.TButton",
                   command=self._exportar_simulacion).pack(fill="x", padx=6, pady=3)

        # ── Bloque identificacion del grupo ───────────────────────────────
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))

        info_lines = [
            ("TP4  -  GRUPO 16",  ACCENT2, 9, "bold"),
            ("",                  FG_DIM,  4, "normal"),
            ("INTEGRANTES:",      FG_DIM,  8, "bold"),
        ]
        integrantes = [
            ("Lopez",      "Dario Gustavo",    "26413", "dario477@gmail.com"),
            ("Primo",      "Gabriela A",       "23396", "gabriela17primo@gmail.com"),
            ("Quinones",   "Lautaro Ezequiel", "90172", "ezequiel.lauti02@gmail.com"),
            ("Riera",      "Lucas Santiago",   "91194", "santilrier@gmail.com"),
            ("Paglino",    "Luciano Ivo",      "95738", "lupaglino@gmail.com"),
            ("Soto Garay", "Franco Nicolas",   "95096", "nicolassotogaray@gmail.com"),
            ("Moro",       "Emiliano",         "96237", "emimoro2003@gmail.com"),
            ("Tacca",      "Franco",           "94189", "fr.tacca@gmail.com"),
        ]

        for text, color, size, weight in info_lines:
            if text == "":
                tk.Frame(inner, bg=BG_DARK, height=2).pack()
                continue
            tk.Label(inner, text=text, bg=BG_DARK, fg=color,
                     font=("Consolas", size, weight),
                     anchor="w").pack(fill="x", padx=8, pady=0)

        for apellido, nombre, legajo, mail in integrantes:
            blk = tk.Frame(inner, bg=BG_CARD)
            blk.pack(fill="x", padx=6, pady=1)
            tk.Label(blk, text=apellido + " " + nombre,
                     bg=BG_CARD, fg=FG_MAIN,
                     font=("Consolas", 8, "bold"),
                     anchor="w").pack(fill="x", padx=6, pady=(3, 0))
            row2 = tk.Frame(blk, bg=BG_CARD)
            row2.pack(fill="x", padx=6, pady=(0, 3))
            tk.Label(row2, text="Leg. " + legajo,
                     bg=BG_CARD, fg=ACCENT,
                     font=("Consolas", 7),
                     anchor="w", width=10).pack(side="left")
            tk.Label(row2, text=mail,
                     bg=BG_CARD, fg=FG_DIM,
                     font=("Consolas", 7),
                     anchor="w").pack(side="left")

        tk.Frame(inner, bg=BG_DARK, height=12).pack()

    # ── Area de tabla ─────────────────────────────────────────────────────
    def _build_table_area(self, parent):
        outer = tk.Frame(parent, bg=BG_DARK)
        outer.pack(fill="both", expand=True, padx=2, pady=2)
        outer.grid_columnconfigure(0, weight=1)
        # row 0: header canvas
        # row 1: treeview (expande)
        # row 2: ultima fila fija
        # row 3: scrollbar horizontal
        outer.grid_rowconfigure(1, weight=1)

        # Header de grupos
        self._hdr_canvas = tk.Canvas(outer, bg=BG_DARK, height=46,
                                     highlightthickness=0)
        self._hdr_canvas.grid(row=0, column=0, sticky="ew")

        # Treeview principal (filas normales)
        tv_frame = tk.Frame(outer, bg=BG_DARK)
        tv_frame.grid(row=1, column=0, sticky="nsew")
        tv_frame.grid_rowconfigure(0, weight=1)
        tv_frame.grid_columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(tv_frame, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set,
                             xscrollcommand=self._on_tree_xscroll)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Treeview de ultima fila (fijo abajo, sin scroll vertical)
        self._tree_last = ttk.Treeview(outer, show="headings",
                                       selectmode="browse", height=1)
        self._tree_last.grid(row=2, column=0, sticky="ew")
        self._tree_last.configure(xscrollcommand=self._on_last_xscroll)

        # Scrollbar horizontal compartida (controla ambos treeviews)
        self._hsb = ttk.Scrollbar(outer, orient="horizontal",
                                  command=self._on_hscroll)
        self._hsb.grid(row=3, column=0, sticky="ew")

        # Tags
        for tree in (self._tree, self._tree_last):
            tree.tag_configure("odd",    background=ROW_ODD)
            tree.tag_configure("even",   background=ROW_EVEN)
            tree.tag_configure("ultima", background=ROW_LAST, foreground=YELLOW)

        self._col_widths = {}

        # Menus de copia con clic derecho en ambos treeviews
        self.root.after(200, lambda: self._menu_copia_tree(self._tree))
        self.root.after(200, lambda: self._menu_copia_tree(self._tree_last))
        # Menus en todos los Labels (status, params, etc.)
        self.root.after(700, lambda: self._instalar_copia_recursiva(self.root))

    def _arrancar_polling(self):
        if not self._col_polling:
            self._col_polling = True
            self._poll_anchos()

    def _poll_anchos(self):
        """Cada 300ms: si algun ancho de columna cambio, sincroniza header y tree_last."""
        if not self._col_polling or not self._col_widths:
            self.root.after(300, self._poll_anchos)
            return
        cols = self._tree["columns"]
        if not cols:
            self.root.after(300, self._poll_anchos)
            return
        cambio = False
        for col in cols:
            try:
                w = self._tree.column(col, "width")
            except Exception:
                continue
            if w != self._col_widths.get(col, -1):
                self._col_widths[col] = w
                try:
                    self._tree_last.column(col, width=w)
                except Exception:
                    pass
                cambio = True
        if cambio:
            self._dibujar_header(self._params_snapshot)
        self.root.after(300, self._poll_anchos)

    def _on_hscroll(self, *args):
        self._tree.xview(*args)
        self._tree_last.xview(*args)
        self._sync_header()

    def _on_tree_xscroll(self, first, last):
        self._hsb.set(first, last)
        self._tree_last.xview_moveto(first)
        self._sync_header()

    def _on_last_xscroll(self, first, last):
        self._hsb.set(first, last)
        self._tree.xview_moveto(first)
        self._sync_header()

    def _sync_header(self):
        try:
            x1, _ = self._tree.xview()
            self._hdr_canvas.xview_moveto(x1)
        except Exception:
            pass

    # ── Grupos de columnas ────────────────────────────────────────────────
    def _grupos_con_params(self, params):
        mu_ll = params.get("media_llegada",        30)
        t_tr  = params.get("tiempo_triage",          5)
        t_pac = params.get("tiempo_paciencia",      30)
        mu_od = params.get("media_odontologo",      30)
        a_cir = params.get("uniforme_a",            40)
        b_cir = params.get("uniforme_b",            60)
        t_est = params.get("tiempo_esterilizacion", 15)

        return [
            # ITERACION / TIEMPO
            ("i",              GRP_ITER,     ["i"]),
            ("Dia / Hora / Clock", GRP_ITER, ["Dia", "Hora", "Clock (min)"]),
            # EVENTOS
            ("exp neg u=" + str(mu_ll),
                               GRP_LLEGADA,  ["Evento", "RND Llegada", "T Entre Llegadas", "Prox. Llegada"]),
            ("t triage=" + str(t_tr),
                               GRP_TRIAGE,   ["T Triage", "fin_triage"]),
            ("t pac=" + str(t_pac),
                               GRP_ESPER_OD, ["T Espera OD", "fin_espera_od"]),
            ("t pac=" + str(t_pac),
                               GRP_ESPER_CI, ["T Espera Cir", "fin_espera_cir"]),
            ("exp neg u=" + str(mu_od),
                               GRP_OD,       ["RND Odontologo", "T Atencion Od.", "fin_odontologo"]),
            ("u A=" + str(a_cir) + " B=" + str(b_cir),
                               GRP_UNIFORME, ["RND Cirujano", "T Atencion Cir.", "fin_cirujano"]),
            ("t esteril=" + str(t_est),
                               GRP_ESTERIL,  ["T Esterilizacion", "fin_esterilizacion"]),
            ("Derivado",       GRP_DERIV,    ["RND Derivacion", "Derivado A"]),
            ("Se retira",      GRP_RETIRO,   ["RND Retiro", "Se Retira"]),
            # OBJETOS PERMANENTES
            ("TRIAGE",         GRP_PERM,     ["TRIAGE Estado", "TRIAGE Cola"]),
            ("ODONTOLOGO",     GRP_PERM,     ["OD Estado", "OD Cola", "OD Acepta (ctd)"]),
            ("CIRUJANO",       GRP_PERM,     ["CIR Estado", "CIR Cola", "CIR Pac. Atendidos"]),
            # ESTADISTICAS
            ("ESTADISTICAS",   GRP_STAT,     [
                "Llegadas", "Retirados", "% Retirados",
                "Acepta OD", "Acum. Esp. OD (min)", "Prom. Esp. OD (min)",
                "Acum. Libre CIR (min)", "Acum. Atiende CIR (min)",
                "Acum. Esteril. CIR (min)", "Acum. Trabaja CIR (min)",
                "% Atencion CIR", "% Esteriliz. CIR", "% Ocupacion CIR",
            ]),
            # OBJETOS TEMPORALES
            ("OBJETOS TEMPORALES", GRP_TEMP, [
                "CT (Cola Triage)", "T  (En Triage)",
                "CO (Cola Odontologo)", "O  (En Odontologo)",
                "CC (Cola Cirujano)", "C  (En Cirujano)",
            ]),
        ]

    def _dibujar_header(self, params):
        canvas = self._hdr_canvas
        canvas.delete("all")
        if not self._col_widths:
            return

        grupos = self._grupos_con_params(params)

        # Posicion x de cada columna en el mismo orden que el DataFrame
        col_x = {}
        x = 0
        for g in grupos:
            for col in g[2]:
                col_x[col] = x
                x += self._col_widths.get(col, 80)

        total_w = x
        canvas.configure(scrollregion=(0, 0, total_w, 46))

        # ── Fila baja (y 22-46): sub-grupos coloreados ───────────────────
        for label, bg, cols in grupos:
            if not cols:
                continue
            x0 = col_x.get(cols[0], 0)
            x1 = col_x.get(cols[-1], x0) + self._col_widths.get(cols[-1], 80)
            w  = x1 - x0
            if w <= 0:
                continue
            canvas.create_rectangle(x0, 22, x1, 46, fill=bg, outline="#111", width=1)
            canvas.create_text(x0 + w / 2, 34, text=label,
                               font=("Consolas", 7, "bold"), fill=TXT_GRP,
                               anchor="center", width=max(10, w - 4))

        # ── Fila alta (y 0-22): secciones grandes ────────────────────────
        secciones = [
            ("ITERACION / TIEMPO", GRP_ITER,
             [c for g in grupos if g[1] == GRP_ITER for c in g[2]]),
            ("EVENTOS", "#0a2010",
             [c for g in grupos
              if g[1] in (GRP_LLEGADA, GRP_TRIAGE, GRP_ESPER_OD,
                          GRP_ESPER_CI, GRP_OD, GRP_UNIFORME,
                          GRP_ESTERIL, GRP_DERIV, GRP_RETIRO)
              for c in g[2]]),
            ("OBJETOS PERMANENTES", GRP_PERM,
             [c for g in grupos if g[1] == GRP_PERM for c in g[2]]),
            ("ESTADISTICAS", GRP_STAT,
             [c for g in grupos if g[1] == GRP_STAT for c in g[2]]),
            ("OBJETOS TEMPORALES", GRP_TEMP,
             [c for g in grupos if g[1] == GRP_TEMP for c in g[2]]),
        ]

        for label, bg, cols in secciones:
            if not cols:
                continue
            x0 = col_x.get(cols[0], 0)
            x1 = col_x.get(cols[-1], x0) + self._col_widths.get(cols[-1], 80)
            w  = x1 - x0
            if w <= 0:
                continue
            canvas.create_rectangle(x0, 0, x1, 22, fill=bg, outline="#111", width=1)
            canvas.create_text(x0 + w / 2, 11, text=label,
                               font=("Consolas", 8, "bold"), fill="#ffffff",
                               anchor="center", width=max(10, w - 4))

    # ── Ejecutar simulacion ───────────────────────────────────────────────
    def _run(self):
        int_keys = {"max_iteraciones", "pacientes_esterilizar", "cant_mostrar"}
        params = {}

        for key, entry in self._entries.items():
            val = entry.get().strip()
            if not val:
                messagebox.showwarning("Parametro faltante",
                                       "El campo '" + key + "' esta vacio.")
                return
            try:
                params[key] = int(val) if key in int_keys else float(val)
            except ValueError:
                messagebox.showerror("Error de parametro",
                                     "Valor invalido en '" + key + "': " + val)
                return

        # Validaciones
        def warn(msg):
            messagebox.showwarning("Parametro invalido", msg)

        if params.get("media_llegada", 1) <= 0:
            warn("La Media de la Exponencial Negativa (llegada) debe ser mayor a 0.")
            return
        if params.get("media_odontologo", 1) <= 0:
            warn("La Media de la Exponencial Negativa (Odontologo) debe ser mayor a 0.")
            return
        if params.get("tiempo_triage", 1) <= 0:
            warn("El tiempo de atencion en Triage debe ser mayor a 0.")
            return
        a = params.get("uniforme_a", 40)
        b = params.get("uniforme_b", 60)
        if a >= b:
            warn("En la distribucion uniforme, A (" + str(a) + ") debe ser menor a B (" + str(b) + ").")
            return
        if params.get("tiempo_paciencia", 1) <= 0:
            warn("El tiempo de Paciencia debe ser mayor a 0.")
            return
        if params.get("pacientes_esterilizar", 1) <= 0:
            warn("La frecuencia de Esterilizacion no puede ser menor o igual a 0.")
            return
        if params.get("tiempo_esterilizacion", 1) <= 0:
            warn("El tiempo de Esterilizacion debe ser mayor a 0.")
            return
        if params.get("tiempo_max", 1) <= 0:
            warn("El Tiempo maximo de simulacion debe ser mayor a 0.")
            return
        if params.get("max_iteraciones", 1) <= 0:
            warn("El Maximo de Iteraciones debe ser mayor a 0.")
            return
        if params.get("inicio_mostrar", 0) < 0:
            warn("La Hora de inicio de muestra no puede ser negativa.")
            return
        if params.get("cant_mostrar", 1) <= 0:
            warn("La Cantidad de iteraciones a mostrar debe ser mayor a 0.")
            return

        self._params_snapshot = dict(params)

        # Estado: SIMULANDO (amarillo)
        self._lbl_status.configure(text="Simulando...", fg=YELLOW)
        self._lbl_status.update()

        try:
            self._sim = SimulacionGuardiaOdontologica(params)
            filas, ultima, stats = self._sim.simular()
        except Exception as e:
            messagebox.showerror("Error en simulacion", str(e))
            # Estado: ERROR (rojo)
            self._lbl_status.configure(text="Error!", fg=RED)
            return

        self._df_full   = self._sim.to_dataframe(filas)
        filtradas       = self._sim.get_filas_filtradas()
        self._df_filter = self._sim.to_dataframe(filtradas)

        df_last = self._sim.to_dataframe([ultima]) if ultima else pd.DataFrame()
        self._poblar_tree(self._df_filter, df_last)

        # Estado: FIN (verde) — leer i, Dia, Hora, Clock directamente de la ultima fila
        uf  = self._sim.ultima_fila or {}
        n   = uf.get("iteracion", stats.get("iteraciones_totales", 0))
        dia = uf.get("dia", 1)
        h   = uf.get("hora", 0.0)
        m   = uf.get("clock", 0.0)
        self._lbl_status.configure(
            text=str(n) + " i |  Dia " + str(dia)
                 + "  |  " + str(h) + " h  |  " + str(m) + " min",
            fg=GREEN
        )

    def _poblar_tree(self, df, df_last=None):
        self._tree.delete(*self._tree.get_children())
        self._tree_last.delete(*self._tree_last.get_children())
        self._col_widths = {}

        if df is None or df.empty:
            self._tree["columns"] = []
            self._tree_last["columns"] = []
            self._hdr_canvas.delete("all")
            return

        cols = list(df.columns)

        # Configurar ambos treeviews con las mismas columnas y anchos
        for tree in (self._tree, self._tree_last):
            tree["columns"] = cols
            for col in cols:
                tree.heading(col, text=col, anchor="center")
                w = max(75, min(160, len(col) * 8 + 16))
                tree.column(col, width=w, minwidth=50, stretch=False, anchor="center")
        # Guardar anchos una sola vez
        for col in cols:
            self._col_widths[col] = max(75, min(160, len(col) * 8 + 16))

        # Filas normales — sin colorado especial, solo alternado
        for idx, row in df.iterrows():
            values = [str(v) if pd.notna(v) else "-" for v in row]
            tag = "even" if idx % 2 == 0 else "odd"
            self._tree.insert("", "end", values=values, tags=(tag,))

        # Ultima fila fija en el treeview inferior
        if df_last is not None and not df_last.empty:
            row = df_last.iloc[0]
            values = [str(v) if pd.notna(v) else "-" for v in row]
            self._tree_last.insert("", "end", values=values, tags=("ultima",))

        # Dibujar header y arrancar polling de anchos
        self._tree.after(100, lambda: self._dibujar_header(self._params_snapshot))
        self._tree.after(400, self._arrancar_polling)

    # ── Copia con clic derecho ───────────────────────────────────────────
    def _menu_copia_label(self, widget):
        """Instala menu clic derecho en un Label para copiar su texto."""
        m = tk.Menu(widget, tearoff=0, bg=BG_CARD, fg=FG_MAIN,
                    activebackground=ACCENT, activeforeground=BG_DARK,
                    font=("Consolas", 9))
        def _cop():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(widget.cget("text"))
            except Exception:
                pass
        m.add_command(label="Copiar", command=_cop)
        def _show(e):
            try:    m.tk_popup(e.x_root, e.y_root)
            finally: m.grab_release()
        widget.bind("<Button-3>", _show)

    def _menu_copia_tree(self, tree):
        """Instala menu clic derecho en un Treeview para copiar fila o tabla."""
        m = tk.Menu(tree, tearoff=0, bg=BG_CARD, fg=FG_MAIN,
                    activebackground=ACCENT, activeforeground=BG_DARK,
                    font=("Consolas", 9))
        def _cop_fila():
            sel = tree.selection()
            if not sel:
                return
            cols = tree["columns"]
            vals = tree.item(sel[0], "values")
            txt  = "	".join(str(c) for c in cols) + chr(10) + "	".join(str(v) for v in vals)
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
        def _cop_tabla():
            cols = tree["columns"]
            filas = ["	".join(str(c) for c in cols)]
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                filas.append("	".join(str(v) for v in vals))
            self.root.clipboard_clear()
            self.root.clipboard_append(chr(10).join(filas))
        m.add_command(label="Copiar fila seleccionada", command=_cop_fila)
        m.add_command(label="Copiar tabla completa",    command=_cop_tabla)
        def _show(e):
            iid = tree.identify_row(e.y)
            if iid:
                tree.selection_set(iid)
            try:    m.tk_popup(e.x_root, e.y_root)
            finally: m.grab_release()
        tree.bind("<Button-3>", _show)

    def _instalar_copia_recursiva(self, widget):
        """Recorre todos los hijos e instala menu en cada Label."""
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                self._menu_copia_label(child)
            self._instalar_copia_recursiva(child)

    # ── Estadisticas finales ──────────────────────────────────────────────
    def _dibujar_donut(self, canvas, pct_at, pct_es, pct_libre):
        """Dibuja un grafico donut minimalista en el canvas dado."""
        import math
        W, H = 180, 180
        cx, cy = W // 2, H // 2
        r_out, r_in = 72, 42
        bg = BG_CARD

        # Colores del donut (igual al de la imagen de referencia)
        colores = [
            ("#4fc3f7", pct_at,     "Atendiendo"),   # azul
            ("#ce93d8", pct_es,     "Esteriliz."),   # violeta
            ("#546e7a", pct_libre,  "Libre"),         # gris azulado
        ]

        def _arco(start_deg, end_deg, color):
            # Dibujar arco como poligono de muchos puntos
            steps = max(int(abs(end_deg - start_deg)), 2)
            points = []
            for i in range(steps + 1):
                a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
                points.append(cx + r_out * math.cos(a))
                points.append(cy + r_out * math.sin(a))
            for i in range(steps + 1):
                a = math.radians(end_deg - (end_deg - start_deg) * i / steps)
                points.append(cx + r_in * math.cos(a))
                points.append(cy + r_in * math.sin(a))
            if len(points) >= 6:
                canvas.create_polygon(points, fill=color, outline=bg, width=3, smooth=False)

        # Dibujar fondo del circulo
        canvas.create_oval(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                           fill="#2a3050", outline="")
        canvas.create_oval(cx - r_in,  cy - r_in,  cx + r_in,  cy + r_in,
                           fill=bg, outline="")

        angle = -90.0   # empezar desde arriba
        for color, pct, _ in colores:
            if pct <= 0:
                continue
            sweep = pct / 100.0 * 360.0
            _arco(angle, angle + sweep, color)
            angle += sweep

        # Agujero central limpio
        canvas.create_oval(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                           fill=bg, outline="")

    def _ver_estadisticas(self):
        if not (self._sim and self._sim.estadisticas):
            messagebox.showinfo("Sin datos", "Ejecute la simulacion primero.")
            return
        s   = self._sim.estadisticas
        win = tk.Toplevel(self.root)
        win.title("Estadísticas Finales  -  Guardia Odontológica Sonrisas")
        win.configure(bg=BG_DARK)
        win.geometry("620x900")
        win.resizable(True, True)

        tk.Label(win, text="RESULTADOS DE LA SIMULACIÓN",
                 bg=BG_DARK, fg=ACCENT,
                 font=("Consolas", 14, "bold")).pack(pady=(18, 4))
        tk.Label(win,
                 text=("Tiempo simulado: " + str(s["tiempo_simulado"]) + " min   |   "
                       + "Iteraciones: " + str(s["iteraciones_totales"])),
                 bg=BG_DARK, fg=FG_DIM,
                 font=("Consolas", 10)).pack(pady=(0, 10))

        def _card(parent, title):
            f = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
            f.pack(fill="x", padx=20, pady=5)
            tk.Label(f, text=title, bg=BG_CARD, fg=ACCENT2,
                     font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
            return f

        def _row_detail(parent, lbl, val, col):
            r = tk.Frame(parent, bg=BG_CARD)
            r.pack(fill="x", padx=14, pady=1)
            tk.Label(r, text=lbl, bg=BG_CARD, fg=FG_DIM,
                     font=("Consolas", 10), width=26, anchor="w").pack(side="left")
            tk.Label(r, text=str(val), bg=BG_CARD, fg=col,
                     font=("Consolas", 10, "bold")).pack(side="left")

        def _row_result(parent, lbl, val, col):
            """Resultado principal: etiqueta mediana + valor grande en negrita."""
            r = tk.Frame(parent, bg=BG_CARD)
            r.pack(fill="x", padx=14, pady=(4, 8))
            tk.Label(r, text=lbl, bg=BG_CARD, fg=col,
                     font=("Consolas", 12, "bold")).pack(anchor="w")
            tk.Label(r, text=str(val), bg=BG_CARD, fg=col,
                     font=("Consolas", 26, "bold")).pack(anchor="w")

        # ── Consigna A ────────────────────────────────────────────────────
        cA = _card(win, "CONSIGNA A  -  Abandono por impaciencia")
        _row_detail(cA, "Total llegadas",   s["total_llegadas"],  FG_MAIN)
        _row_detail(cA, "Total retirados",  s["total_retirados"], RED)
        _row_result(cA, "% Pacientes retirados", str(s["pct_retirados"]) + "%", RED)

        # ── Consigna B ────────────────────────────────────────────────────
        cB = _card(win, "CONSIGNA B  -  Espera Odontólogo General")
        _row_detail(cB, "Pacientes que aceptaron",  s["cnt_acepta_od"],  GREEN)
        _row_detail(cB, "Acum. tiempo cola (min)",  s["acum_espera_od"], ACCENT)
        _row_result(cB, "Prom. espera cola (min)", str(s["prom_espera_od"]) + " min", GREEN)

        # ── Consigna C ────────────────────────────────────────────────────
        cC = _card(win, "CONSIGNA C  -  Ocupación Cirujano")

        # Acumuladores (detalle)
        tk.Label(cC, text="  ACUMULADORES", bg=BG_CARD, fg=FG_DIM,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=8, pady=(2, 0))
        for lbl, val, col in [
            ("Libre (min)",          s["acum_libre_cir"],   FG_DIM),
            ("Atendiendo (min)",     s["acum_atiende_cir"], ACCENT),
            ("Esterilizando (min)",  s["acum_esteril_cir"], PURPLE),
            ("Trabaja L+A+E (min)",  s["acum_trabaja_cir"], YELLOW),
        ]:
            _row_detail(cC, lbl, val, col)

        # Fila inferior: porcentajes grandes + donut
        rowC_bot = tk.Frame(cC, bg=BG_CARD)
        rowC_bot.pack(fill="x", padx=12, pady=(6, 10))

        # Porcentajes (izquierda)
        colC_pcts = tk.Frame(rowC_bot, bg=BG_CARD)
        colC_pcts.pack(side="left", fill="y", padx=(0, 10))
        for lbl, val, col in [
            ("% Atendiendo",   str(s["pct_atiende_cir"]) + "%", ACCENT),
            ("% Esterilizando",str(s["pct_esteril_cir"]) + "%", PURPLE),
            ("% Ocupacion",    str(s["pct_ocup_cir"])    + "%", GREEN),
        ]:
            r = tk.Frame(colC_pcts, bg=BG_CARD)
            r.pack(anchor="w", pady=3)
            tk.Label(r, text=lbl, bg=BG_CARD, fg=col,
                     font=("Consolas", 11, "bold")).pack(anchor="w")
            tk.Label(r, text=val, bg=BG_CARD, fg=col,
                     font=("Consolas", 22, "bold")).pack(anchor="w")

        # Donut (derecha)
        colC_donut = tk.Frame(rowC_bot, bg=BG_CARD)
        colC_donut.pack(side="left", fill="both", expand=True, padx=(10, 0))

        donut_cv = tk.Canvas(colC_donut, width=180, height=180,
                             bg=BG_CARD, highlightthickness=0)
        donut_cv.pack(anchor="center")

        pct_at     = s["pct_atiende_cir"]
        pct_es     = s["pct_esteril_cir"]
        pct_libre  = round(100.0 - pct_at - pct_es, 2)
        self._dibujar_donut(donut_cv, pct_at, pct_es, pct_libre)

        # Leyenda del donut
        leyenda = tk.Frame(colC_donut, bg=BG_CARD)
        leyenda.pack(pady=(4, 0))
        for color, lbl, val in [
            ("#4fc3f7", "Atend.",  str(pct_at)    + "%"),
            ("#ce93d8", "Esteril.",str(pct_es)    + "%"),
            ("#546e7a", "Libre",   str(pct_libre) + "%"),
        ]:
            entry = tk.Frame(leyenda, bg=BG_CARD)
            entry.pack(side="left", padx=6)
            tk.Frame(entry, bg=color, width=10, height=10).pack(side="left", padx=(0, 3))
            tk.Label(entry, text=lbl + " " + val, bg=BG_CARD, fg=FG_DIM,
                     font=("Consolas", 7)).pack(side="left")

        ttk.Button(win, text="Cerrar", style="Run.TButton",
                   command=win.destroy).pack(pady=14)

    # ── Exportar a Excel ──────────────────────────────────────────────────
    def _exportar_simulacion(self):
        if self._df_full is None or self._df_full.empty:
            messagebox.showinfo("Sin datos", "Ejecute la simulacion primero.")
            return
        path = os.path.join(os.path.expanduser("~"), "simulacion_sonrisas.xlsx")
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                self._df_full.to_excel(writer, sheet_name="Vector de Estado", index=False)
                if self._df_filter is not None and not self._df_filter.empty:
                    self._df_filter.to_excel(writer, sheet_name="Filtrado (j,i)", index=False)
                if self._sim and self._sim.ultima_fila:
                    self._sim.to_dataframe([self._sim.ultima_fila]).to_excel(
                        writer, sheet_name="Ultima Fila", index=False)
                if self._sim and self._sim.estadisticas:
                    pd.DataFrame(
                        list(self._sim.estadisticas.items()),
                        columns=["Indicador", "Valor"]
                    ).to_excel(writer, sheet_name="Estadisticas", index=False)
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))
            return

        resp = messagebox.askyesno("Exportacion exitosa",
                                   "Guardado en:\n" + path + "\n\n¿Abrir ahora?")
        if resp:
            try:
                if os.name == "nt":
                    os.startfile(path)
                else:
                    subprocess.call(["open", path])
            except Exception:
                pass

    def _abrir_excel(self):
        self._exportar_simulacion()

    def _ver_ultima_fila(self):
        pass


if __name__ == "__main__":
    root = tk.Tk()
    AppSimulacion(root)
    root.mainloop()
