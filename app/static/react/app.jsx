const { useEffect, useLayoutEffect, useMemo, useRef, useState } = React;

// nav: flat items are [path, label], dropdown items are {label, items: [[path, label], ...]}
const routes = [
  { label: "ATLETAS", items: [
    ["/atletas", "Listagem"],
    ["/cadastros", "Cadastro"],
  ]},
  { label: "ACADEMIAS", items: [
    ["/academias", "Listagem"],
    ["/equipes", "Cadastro"],
  ]},
  ["/categorias", "CATEGORIAS"],
  ["/config-categorias", "CONFIG. CATEGORIAS"],
  ["/ordem", "ORDEM DE LUTAS"],
  ["/competicoes", "CHAMPIONSHIPS"],
  ["/inscricoes", "REGISTRATION"],
  ["/chaves", "GERAR CHAVES"],
  ["/chaves/salvas", "CHAVES SALVAS"],
  ["/cronograma", "CRONOGRAMA"],
  ["/checagem", "LISTAGEM DE ATLETAS"],
  ["/checkin/pesagem", "PESAGEM"],
  ["/checkin", "CHECKIN"],
  ["/checagem-final", "CHECAGEM FINAL"],
  ["/ranking", "RANKING"],
];

const beltLabels = {
  white: "Branca",
  gray: "Cinza",
  gray_white: "Cinza-branca",
  gray_black: "Cinza-preta",
  yellow: "Amarela",
  yellow_white: "Amarela-branca",
  yellow_black: "Amarela-preta",
  orange: "Laranja",
  orange_white: "Laranja-branca",
  orange_black: "Laranja-preta",
  green: "Verde",
  green_white: "Verde-branca",
  green_black: "Verde-preta",
  blue: "Azul",
  purple: "Roxa",
  brown: "Marrom",
  black: "Preta",
  red_black: "Vermelha e preta / coral",
  red_white: "Vermelha e branca / coral",
  red: "Vermelha",
};

const beltOptions = Object.entries(beltLabels);
const BELTS_ABOVE_BLACK = new Set(["red_black", "red_white", "red"]);

const sexLabels = {
  male: "Masculino",
  female: "Feminino",
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = Array.isArray(body.detail)
        ? body.detail.map((item) => item.msg).join("; ")
        : body.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.status === 204 ? null : response.json();
}

function pdfFileName(bracket, suffix = "") {
  return `fjjpe-${categoryLabel(bracket.category)}${suffix ? `-${suffix}` : ""}`
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

async function exportBracketPdf(element, bracket, suffix = "") {
  if (!window.html2canvas || !window.jspdf?.jsPDF) {
    throw new Error("Bibliotecas de PDF ainda nao carregaram. Tente novamente em alguns segundos.");
  }

  await new Promise((resolve) => requestAnimationFrame(resolve));

  const canvas = await window.html2canvas(element, {
    backgroundColor: "#ffffff",
    scale: Math.min(2, window.devicePixelRatio || 1.5),
    useCORS: true,
    windowWidth: element.scrollWidth,
    windowHeight: element.scrollHeight,
  });
  const pdf = new window.jspdf.jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 4;
  const availableWidth = pageWidth - margin * 2;
  const availableHeight = pageHeight - margin * 2;
  const ratio = Math.min(availableWidth / canvas.width, availableHeight / canvas.height);
  const imageWidth = canvas.width * ratio;
  const imageHeight = canvas.height * ratio;
  const x = (pageWidth - imageWidth) / 2;
  const y = (pageHeight - imageHeight) / 2;

  pdf.addImage(canvas.toDataURL("image/png"), "PNG", x, y, imageWidth, imageHeight);
  pdf.save(`${pdfFileName(bracket, suffix)}.pdf`);
}

function normalizeCpf(value) {
  return value.replace(/\D/g, "");
}

function maskCpf(value) {
  return normalizeCpf(value)
    .slice(0, 11)
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function maskAthletePhone(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/(\d{2})(\d)/, "$1-$2")
    .replace(/(\d{5})(\d{1,4})$/, "$1.$2");
}

function maskTeamPhone(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/(\d{2})(\d)/, "$1-$2")
    .replace(/(\d{5})(\d{1,4})$/, "$1-$2");
}

function isValidCpf(value) {
  const digits = normalizeCpf(value);
  if (digits.length !== 11 || digits === digits[0].repeat(11)) return false;
  const numbers = [...digits].map(Number);
  const firstSum = numbers.slice(0, 9).reduce((total, number, index) => {
    return total + number * (10 - index);
  }, 0);
  let firstDigit = (firstSum * 10) % 11;
  if (firstDigit === 10) firstDigit = 0;
  const secondSum = numbers.slice(0, 10).reduce((total, number, index) => {
    return total + number * (11 - index);
  }, 0);
  let secondDigit = (secondSum * 10) % 11;
  if (secondDigit === 10) secondDigit = 0;
  return numbers[9] === firstDigit && numbers[10] === secondDigit;
}

function categoryLabel(category) {
  return `${category.age_group} | ${beltLabels[category.belt] || category.belt} | ${category.weight_class}`;
}

function formatScheduleTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatScheduleDay(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
}

function Message({ text, type }) {
  return <p className={`message ${type || ""}`.trim()} role="status" aria-live="polite">{text}</p>;
}

async function loadAllTeams() {
  const limit = 100;
  let offset = 0;
  let items = [];
  let total = 0;
  do {
    const page = await fetchJson(`/teams?limit=${limit}&offset=${offset}`);
    items = [...items, ...page.items];
    total = page.total;
    offset += limit;
  } while (items.length < total);
  return items.sort((a, b) => a.name.localeCompare(b.name));
}

function App() {
  const path = window.location.pathname === "/" ? "/cadastros" : window.location.pathname;
  const bracketRouteMatch = path.match(/^\/chaves\/(\d+)$/);
  const bracketRouteId = bracketRouteMatch ? Number(bracketRouteMatch[1]) : null;
  const [apiOk, setApiOk] = useState(false);
  const [openNavDropdown, setOpenNavDropdown] = useState("");

  useEffect(() => {
    fetchJson("/health").then(() => setApiOk(true)).catch(() => setApiOk(false));
  }, []);

  const athleteEditMatch = path.match(/^\/atletas\/(\d+)$/);
  const athleteEditId = athleteEditMatch ? Number(athleteEditMatch[1]) : null;
  const academyEditMatch = path.match(/^\/academias\/(\d+)$/);
  const academyEditId = academyEditMatch ? Number(academyEditMatch[1]) : null;

  function findRouteLabel(p) {
    for (const r of routes) {
      if (Array.isArray(r) && r[0] === p) return r[1];
      if (r.items) { const found = r.items.find(([rp]) => rp === p); if (found) return found[1]; }
    }
    return null;
  }

  const title = bracketRouteId
    ? `CHAVE #${bracketRouteId}`
    : athleteEditId
      ? `EDITAR ATLETA #${athleteEditId}`
      : academyEditId
        ? `EDITAR ACADEMIA #${academyEditId}`
        : (findRouteLabel(path) || "ATHLETES");

  const isBracket = path === "/chaves" || path === "/chaves/salvas" || Boolean(bracketRouteId);
  const isCategorias = path === "/categorias";
  const isOrdem = path === "/ordem";

  const knownPaths = [
    "/atletas", "/cadastros", "/categorias", "/config-categorias", "/ordem",
    "/academias", "/equipes", "/competicoes", "/inscricoes", "/chaves", "/chaves/salvas",
    "/cronograma", "/checagem", "/checkin/pesagem", "/checkin", "/checagem-final", "/ranking",
  ];

  return (
    <>
      <header className="ibjjf-mainbar">
        <a className="brand" href="/atletas" aria-label="FJJPE">
          <img className="brand-logo" src="/static/fjjpe-logo.png" alt="FJJPE" />
          <strong>FJJPE</strong>
        </a>
        <nav className="site-nav" aria-label="Principal">
          {routes.map((r) => {
            if (Array.isArray(r)) {
              return (
                <a className={r[0] === path ? "active" : ""} href={r[0]} key={r[0]}>{r[1]}</a>
              );
            }
            // dropdown
            const isActive = r.items.some(([rp]) =>
              rp === path ||
              (rp === "/atletas" && Boolean(athleteEditId)) ||
              (rp === "/academias" && Boolean(academyEditId))
            );
            const isOpen = openNavDropdown === r.label;
            return (
              <div className={`nav-dropdown ${isActive ? "active" : ""} ${isOpen ? "open" : ""}`.trim()} key={r.label}>
                <button
                  className="nav-dropdown-trigger"
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => setOpenNavDropdown(isOpen ? "" : r.label)}
                >
                  {r.label} &#9660;
                </button>
                <div className="nav-dropdown-menu">
                  {r.items.map(([rp, rl]) => (
                    <a key={rp} href={rp} className={rp === path ? "active" : ""}>{rl}</a>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>
        <div className={`status top-status ${apiOk ? "ok" : ""}`}>{apiOk ? "Online" : "Conectando"}</div>
      </header>
      <section className="page-title-band">
        <h1>{title}</h1>
      </section>
      <main className={`shell ${isBracket ? "bracket-shell" : ""} ${isCategorias ? "categorias-shell" : ""} ${isOrdem ? "ordem-shell" : ""}`.trim()}>
        {path === "/atletas" && <AtletasListPage />}
        {path === "/cadastros" && <AthletesPage />}
        {athleteEditId && <AtletaEditPage athleteId={athleteEditId} />}
        {path === "/academias" && <AcademiesListPage />}
        {academyEditId && <AcademyEditPage teamId={academyEditId} />}
        {path === "/categorias" && <CategoriasPage />}
        {path === "/config-categorias" && <ConfigCategoriasPage />}
        {path === "/ordem" && <OrdemPage />}
        {path === "/equipes" && <TeamsPage />}
        {path === "/competicoes" && <CompetitionsPage />}
        {path === "/inscricoes" && <RegistrationsPage />}
        {path === "/chaves" && <BracketsPage />}
        {path === "/chaves/salvas" && <SavedBracketsPage />}
        {path === "/cronograma" && <SchedulePage />}
        {bracketRouteId && <BracketByIdPage bracketId={bracketRouteId} />}
        {path === "/checagem" && <AthleteListPage />}
        {path === "/checkin/pesagem" && <WeighinPage />}
        {path === "/checkin" && <CheckinPage />}
        {path === "/checagem-final" && <FinalCheckPage />}
        {path === "/ranking" && <RankingPage />}
        {!bracketRouteId && !athleteEditId && !academyEditId && ![...knownPaths].includes(path) && <AthletesPage />}
      </main>
    </>
  );
}

function AtletasListPage() {
  const [athletes, setAthletes] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(["", ""]);
  const PAGE_SIZE = 50;
  const [offset, setOffset] = useState(0);

  async function load(off = 0, q = search) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: PAGE_SIZE, offset: off });
      const data = await fetchJson(`/athletes?${params}`);
      setAthletes(data.items);
      setTotal(data.total);
      setOffset(off);
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(0); }, []);

  const filtered = athletes.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.name.toLowerCase().includes(q) ||
      a.cpf.includes(q) ||
      (a.team?.name || "").toLowerCase().includes(q)
    );
  });

  function formatDate(d) {
    if (!d) return "-";
    const [y, m, day] = d.split("-");
    return `${day}/${m}/${y}`;
  }

  return (
    <section className="workspace stack">
      <section className="panel atletas-list-panel">
        <div className="section-heading">
          <h2>Atletas Cadastrados</h2>
          <span>{total} atleta(s) no total</span>
        </div>
        <div className="filters single" style={{marginBottom: "14px"}}>
          <input
            type="search"
            placeholder="Buscar por nome, CPF ou academia..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{width:"100%"}}
          />
        </div>
        {loading && <p className="message">Carregando...</p>}
        <Message text={message[0]} type={message[1]} />
        {!loading && (
          <div className="checkin-table-wrap">
            <table className="checkin-table atletas-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>CPF</th>
                  <th>Nascimento</th>
                  <th>Faixa</th>
                  <th>Academia</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan="6" style={{textAlign:"center",color:"var(--muted)"}}>Nenhum atleta encontrado.</td></tr>
                )}
                {filtered.map((a) => (
                  <tr key={a.id}>
                    <td data-label="Nome">{a.name}</td>
                    <td data-label="CPF">{a.cpf}</td>
                    <td data-label="Nascimento">{formatDate(a.birth_date)}</td>
                    <td data-label="Faixa">{beltLabels[a.belt] || a.belt}</td>
                    <td data-label="Academia">{a.team?.name || <span style={{color:"var(--muted)"}}>Sem academia</span>}</td>
                    <td data-label="Editar">
                      <a className="atleta-edit-btn" href={`/atletas/${a.id}`} title="Editar">&#9998;</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="atletas-pagination">
            <button className="secondary compact-button" disabled={offset === 0} onClick={() => load(offset - PAGE_SIZE)}>&#171; Anterior</button>
            <span>{Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(total / PAGE_SIZE)}</span>
            <button className="secondary compact-button" disabled={offset + PAGE_SIZE >= total} onClick={() => load(offset + PAGE_SIZE)}>Proxima &#187;</button>
          </div>
        )}
      </section>
    </section>
  );
}

function AtletaEditPage({ athleteId }) {
  const [form, setForm] = useState(null);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    Promise.all([
      fetchJson(`/athletes/${athleteId}`),
      loadAllTeams(),
    ]).then(([athlete, teamsList]) => {
      setForm({
        name: athlete.name,
        cpf: athlete.cpf,
        email: athlete.email,
        phone: athlete.phone,
        sex: athlete.sex,
        team_id: athlete.team_id ? String(athlete.team_id) : "",
        belt: athlete.belt,
        graduation_date: athlete.graduation_date,
        birth_date: athlete.birth_date,
      });
      setTeams(teamsList);
      setLoading(false);
    }).catch((err) => {
      setMessage([err.message, "error"]);
      setLoading(false);
    });
  }, [athleteId]);

  async function submit(e) {
    e.preventDefault();
    if (form.belt !== "black" && !form.team_id) {
      setMessage(["Selecione a academia do atleta.", "error"]);
      return;
    }
    setSaving(true);
    setMessage(["", ""]);
    try {
      const payload = {
        ...form,
        team_id: form.team_id ? Number(form.team_id) : null,
      };
      await fetchJson(`/athletes/${athleteId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setMessage(["Cadastro atualizado com sucesso.", "success"]);
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="message" style={{padding:"24px"}}>Carregando atleta...</p>;
  if (!form) return <Message text={message[0]} type={message[1]} />;

  return (
    <section className="workspace stack">
      <form className="registration" onSubmit={submit}>
        <div className="section-heading">
          <h2>Alterar Cadastro de Atleta</h2>
          <a href="/atletas" className="button-link secondary" style={{fontSize:"13px"}}>&#171; Voltar</a>
        </div>
        <div className="grid">
          <Field label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />
          <label className="field">
            <span>CPF</span>
            <input value={form.cpf} onChange={(e) => setForm({ ...form, cpf: maskCpf(e.target.value) })} required />
          </label>
          <Field label="Email" type="email" value={form.email} onChange={(email) => setForm({ ...form, email })} required />
          <Field label="Telefone" value={form.phone} onChange={(phone) => setForm({ ...form, phone: maskAthletePhone(phone) })} required />
          <Select label="Sexo" value={form.sex} onChange={(sex) => setForm({ ...form, sex })} required options={[
            ["", "Selecione"],
            ["male", "Masculino"],
            ["female", "Feminino"],
          ]} />
          <Select label="Academia" value={form.team_id} onChange={(team_id) => setForm({ ...form, team_id })} required={form.belt !== "black"} options={[
            ["", form.belt === "black" ? "Sem academia (faixa preta)" : "Selecione a academia"],
            ...teams.map((t) => [String(t.id), t.name]),
          ]} />
          <Select label="Faixa" value={form.belt} onChange={(belt) => setForm({ ...form, belt })} required options={[
            ["", "Selecione"],
            ...beltOptions,
          ]} />
          <Field label="Data da graduacao" type="date" value={form.graduation_date} onChange={(graduation_date) => setForm({ ...form, graduation_date })} required />
          <Field label="Data de nascimento" type="date" value={form.birth_date} onChange={(birth_date) => setForm({ ...form, birth_date })} required />
        </div>
        <div className="actions">
          <a href="/atletas" className="button-link secondary">Cancelar</a>
          <button className="primary" type="submit" disabled={saving}>
            {saving ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
    </section>
  );
}

function AthletesPage() {
  const emptyForm = {
    name: "",
    cpf: "",
    email: "",
    phone: "",
    sex: "",
    team_id: "",
    belt: "",
    graduation_date: "",
    birth_date: "",
  };
  const [form, setForm] = useState(emptyForm);
  const [teams, setTeams] = useState([]);
  const [message, setMessage] = useState(["", ""]);
  const [loading, setLoading] = useState(false);
  const [cpfError, setCpfError] = useState("");

  useEffect(() => {
    loadAllTeams().then(setTeams).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function validateCpfOnBlur() {
    if (!form.cpf) {
      setCpfError("");
      return true;
    }
    if (!isValidCpf(form.cpf)) {
      setCpfError("Informe um CPF valido.");
      setMessage(["CPF invalido. Verifique os digitos informados.", "error"]);
      return false;
    }
    const result = await fetchJson(`/athletes/check-cpf?cpf=${encodeURIComponent(normalizeCpf(form.cpf))}`);
    if (result.exists) {
      setCpfError("CPF ja cadastrado para outro atleta.");
      setMessage(["CPF ja cadastrado para outro atleta.", "error"]);
      return false;
    }
    setCpfError("");
    setMessage(["", ""]);
    return true;
  }

  async function submit(event) {
    event.preventDefault();
    const cpfAvailable = await validateCpfOnBlur();
    if (!cpfAvailable) return;
    if (form.belt !== "black" && !form.team_id) {
      setMessage(["Selecione a academia do atleta.", "error"]);
      return;
    }
    setLoading(true);
    try {
      const athlete = await fetchJson("/athletes", {
        method: "POST",
        body: JSON.stringify({ ...form, team_id: form.team_id ? Number(form.team_id) : null }),
      });
      setMessage([`Atleta ${athlete.name} cadastrado com sucesso.`, "success"]);
      setForm(emptyForm);
    } catch (error) {
      setMessage([error.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace stack">
      <form className="registration" onSubmit={submit}>
        <div className="section-heading">
          <h2>Cadastro de Atletas</h2>
        </div>
        <div className="grid">
          <Field label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />
          <label className="field">
            <span>CPF</span>
            <input
              value={form.cpf}
              onBlur={validateCpfOnBlur}
              onChange={(event) => {
                setCpfError("");
                setForm({ ...form, cpf: maskCpf(event.target.value) });
              }}
              required
              aria-invalid={Boolean(cpfError)}
              title={cpfError || "Informe um CPF valido"}
            />
          </label>
          <Field label="Email" type="email" value={form.email} onChange={(email) => setForm({ ...form, email })} required />
          <Field label="Telefone" value={form.phone} onChange={(phone) => setForm({ ...form, phone: maskAthletePhone(phone) })} required />
          <Select label="Sexo" value={form.sex} onChange={(sex) => setForm({ ...form, sex })} required options={[
            ["", "Selecione"],
            ["male", "Masculino"],
            ["female", "Feminino"],
          ]} />
          <Select label="Academia" value={form.team_id} onChange={(team_id) => setForm({ ...form, team_id })} required={form.belt !== "black"} options={[
            ["", form.belt === "black" ? "Sem academia (faixa preta)" : "Selecione a academia"],
            ...teams.map((t) => [String(t.id), t.name]),
          ]} />
          <Select label="Faixa" value={form.belt} onChange={(belt) => setForm({ ...form, belt })} required options={[
            ["", "Selecione"],
            ...beltOptions,
          ]} />
          <Field label="Data da graduacao" type="date" value={form.graduation_date} onChange={(graduation_date) => setForm({ ...form, graduation_date })} required />
          <Field label="Data de nascimento" type="date" value={form.birth_date} onChange={(birth_date) => setForm({ ...form, birth_date })} required />
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={loading}>Cadastrar atleta</button>
        </div>
        <Message text={cpfError || message[0]} type={cpfError ? "error" : message[1]} />
      </form>
    </section>
  );
}

function AcademiesListPage() {
  const [teams, setTeams] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(["", ""]);
  const PAGE_SIZE = 50;
  const [offset, setOffset] = useState(0);

  async function load(off = 0) {
    setLoading(true);
    try {
      const data = await fetchJson(`/teams?limit=${PAGE_SIZE}&offset=${off}`);
      setTeams(data.items);
      setTotal(data.total);
      setOffset(off);
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(0); }, []);

  const filtered = teams.filter((team) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      team.name.toLowerCase().includes(q) ||
      (team.responsible || "").toLowerCase().includes(q) ||
      team.phone.includes(q)
    );
  });

  function formatDate(value) {
    if (!value) return "-";
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }

  return (
    <section className="workspace stack">
      <section className="panel atletas-list-panel">
        <div className="section-heading">
          <h2>Academias Cadastradas</h2>
          <span>{total} academia(s) no total</span>
        </div>
        <div className="filters single" style={{marginBottom: "14px"}}>
          <input
            type="search"
            placeholder="Buscar por nome, responsavel ou telefone..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            style={{width:"100%"}}
          />
        </div>
        {loading && <p className="message">Carregando...</p>}
        <Message text={message[0]} type={message[1]} />
        {!loading && (
          <div className="checkin-table-wrap">
            <table className="checkin-table atletas-table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Data de criacao</th>
                  <th>Responsavel</th>
                  <th>Telefone</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan="5" style={{textAlign:"center",color:"var(--muted)"}}>Nenhuma academia encontrada.</td></tr>
                )}
                {filtered.map((team) => (
                  <tr key={team.id}>
                    <td data-label="Nome">{team.name}</td>
                    <td data-label="Data de criacao">{formatDate(team.created_date)}</td>
                    <td data-label="Responsavel">{team.responsible || <span style={{color:"var(--muted)"}}>Sem responsavel</span>}</td>
                    <td data-label="Telefone">{team.phone}</td>
                    <td data-label="Editar">
                      <a className="atleta-edit-btn" href={`/academias/${team.id}`} title="Editar">&#9998;</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="atletas-pagination">
            <button className="secondary compact-button" disabled={offset === 0} onClick={() => load(offset - PAGE_SIZE)}>&#171; Anterior</button>
            <span>{Math.floor(offset / PAGE_SIZE) + 1} / {Math.ceil(total / PAGE_SIZE)}</span>
            <button className="secondary compact-button" disabled={offset + PAGE_SIZE >= total} onClick={() => load(offset + PAGE_SIZE)}>Proxima &#187;</button>
          </div>
        )}
      </section>
    </section>
  );
}

function AcademyEditPage({ teamId }) {
  const [form, setForm] = useState(null);
  const [blackBelts, setBlackBelts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    Promise.all([
      fetchJson(`/teams/${teamId}`),
      fetchJson("/athletes?belt=black&limit=100&offset=0"),
    ]).then(([team, blackBeltsPage]) => {
      setForm({
        name: team.name,
        created_date: team.created_date,
        responsible: team.responsible || "",
        phone: team.phone,
      });
      setBlackBelts(blackBeltsPage.items);
      setLoading(false);
    }).catch((err) => {
      setMessage([err.message, "error"]);
      setLoading(false);
    });
  }, [teamId]);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage(["", ""]);
    try {
      const team = await fetchJson(`/teams/${teamId}`, {
        method: "PUT",
        body: JSON.stringify({ ...form, responsible: form.responsible || null }),
      });
      setMessage([`Academia ${team.name} atualizada com sucesso.`, "success"]);
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="message" style={{padding:"24px"}}>Carregando academia...</p>;
  if (!form) return <Message text={message[0]} type={message[1]} />;

  return (
    <section className="workspace stack">
      <form className="registration" onSubmit={submit}>
        <div className="section-heading">
          <h2>Alterar Cadastro de Academia</h2>
          <a href="/academias" className="button-link secondary" style={{fontSize:"13px"}}>&#171; Voltar</a>
        </div>
        <div className="grid">
          <Field label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />
          <Field label="Data de criacao" type="date" value={form.created_date} onChange={(created_date) => setForm({ ...form, created_date })} required />
          <Select label="Responsavel" value={form.responsible} onChange={(responsible) => setForm({ ...form, responsible })} required disabled={!blackBelts.length} options={[
            ["", blackBelts.length ? "Selecione o responsavel" : "Nenhum faixa preta cadastrado"],
            ...blackBelts.map((athlete) => [athlete.name, athlete.name]),
          ]} />
          <Field label="Telefone" value={form.phone} onChange={(phone) => setForm({ ...form, phone: maskTeamPhone(phone) })} required />
        </div>
        <div className="actions">
          <a href="/academias" className="button-link secondary">Cancelar</a>
          <button className="primary" type="submit" disabled={saving || !blackBelts.length}>
            {saving ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
    </section>
  );
}

function TeamsPage() {
  const [form, setForm] = useState({ name: "", created_date: "", responsible: "", phone: "" });
  const [blackBelts, setBlackBelts] = useState([]);
  const [message, setMessage] = useState(["", ""]);
  const [loading, setLoading] = useState(false);

  async function loadBlackBelts() {
    const page = await fetchJson("/athletes?belt=black&limit=100&offset=0");
    setBlackBelts(page.items);
  }

  useEffect(() => {
    loadBlackBelts().catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    try {
      const team = await fetchJson("/teams", { method: "POST", body: JSON.stringify(form) });
      setMessage([`Equipe ${team.name} cadastrada com sucesso.`, "success"]);
      setForm({ name: "", created_date: "", responsible: "", phone: "" });
      await loadBlackBelts();
    } catch (error) {
      setMessage([error.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace stack">
      <form className="registration" onSubmit={submit}>
        <div className="section-heading">
          <h2>Cadastro de Equipes</h2>
          <span>{blackBelts.length ? `Faixas pretas: ${blackBelts.length}` : "Carregando faixas pretas"}</span>
        </div>
        <div className="grid">
          <Field label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />
          <Field label="Data de criacao" type="date" value={form.created_date} onChange={(created_date) => setForm({ ...form, created_date })} required />
          <Select label="Responsavel" value={form.responsible} onChange={(responsible) => setForm({ ...form, responsible })} required disabled={!blackBelts.length} options={[
            ["", blackBelts.length ? "Selecione o responsavel" : "Nenhum faixa preta cadastrado"],
            ...blackBelts.map((athlete) => [athlete.name, athlete.name]),
          ]} />
          <Field label="Telefone" value={form.phone} onChange={(phone) => setForm({ ...form, phone: maskTeamPhone(phone) })} required />
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={loading || !blackBelts.length}>Cadastrar equipe</button>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
    </section>
  );
}

function CompetitionsPage() {
  const [form, setForm] = useState({
    name: "",
    event_date: "",
    start_time: "09:00",
    mat_count: "4",
    competition_type: "Oficial",
    competition_days: "2",
  });
  const [count, setCount] = useState(0);
  const [message, setMessage] = useState(["", ""]);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function loadCount() {
    const competitions = await fetchJson("/competitions");
    setCount(competitions.length);
  }

  useEffect(() => {
    loadCount().catch((error) => setMessage([error.message, "error"]));
  }, []);

  function competitionDayDates() {
    if (!form.event_date) return [];
    const startDate = new Date(`${form.event_date}T00:00:00`);
    return Array.from({ length: Number(form.competition_days) }, (_, index) => {
      const nextDate = new Date(startDate);
      nextDate.setDate(startDate.getDate() + index);
      return nextDate.toISOString().slice(0, 10);
    });
  }

  async function createCompetition() {
    try {
      const competition = await fetchJson("/competitions", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          mat_count: Number(form.mat_count),
          competition_days: Number(form.competition_days),
        }),
      });
      setMessage([`Competicao ${competition.name} cadastrada.`, "success"]);
      setForm({
        name: "",
        event_date: "",
        start_time: "09:00",
        mat_count: "4",
        competition_type: "Oficial",
        competition_days: "2",
      });
      setConfirmOpen(false);
      await loadCount();
    } catch (error) {
      setConfirmOpen(false);
      setMessage([error.message, "error"]);
    }
  }

  function submit(event) {
    event.preventDefault();
    setConfirmOpen(true);
  }

  return (
    <section className="workspace stack">
      <form className="registration" onSubmit={submit}>
        <div className="section-heading">
          <h2>Nova Competicao</h2>
          <span>Competicoes: {count}</span>
        </div>
        <div className="grid">
          <Field label="Nome" value={form.name} onChange={(name) => setForm({ ...form, name })} required />
          <Field label="Data" type="date" value={form.event_date} onChange={(event_date) => setForm({ ...form, event_date })} required />
          <Field label="Hora de inicio" type="time" value={form.start_time} onChange={(start_time) => setForm({ ...form, start_time })} required />
          <Select label="Tipo de campeonato" value={form.competition_type} onChange={(competition_type) => setForm({ ...form, competition_type })} required options={[
            ["Oficial", "Oficial"],
            ["Chancelado", "Chancelado"],
          ]} />
          <Select label="Dias de competicao" value={form.competition_days} onChange={(competition_days) => setForm({ ...form, competition_days })} required options={[
            ["1", "1 dia"],
            ["2", "2 dias"],
            ["3", "3 dias"],
          ]} />
          <Select label="MATS" value={form.mat_count} onChange={(mat_count) => setForm({ ...form, mat_count })} required options={[
            ["4", "4 MATS"],
            ["6", "6 MATS"],
            ["8", "8 MATS"],
            ["10", "10 MATS"],
            ["12", "12 MATS"],
          ]} />
        </div>
        <div className="actions"><button className="primary" type="submit">Cadastrar competicao</button></div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {confirmOpen && (
        <div className="modal-backdrop" role="alertdialog" aria-modal="true">
          <section className="fight-confirm">
            <h2>Confirmar criacao da competicao?</h2>
            <p><strong>Nome:</strong> {form.name}</p>
            <p><strong>Data inicial:</strong> {form.event_date}</p>
            <p><strong>Hora de inicio:</strong> {form.start_time}</p>
            <p><strong>Tipo:</strong> {form.competition_type}</p>
            <p><strong>Dias:</strong> {form.competition_days}</p>
            <p><strong>Datas inferidas:</strong> {competitionDayDates().join(", ")}</p>
            <p><strong>MATS:</strong> {form.mat_count}</p>
            <div className="actions">
              <button className="secondary" type="button" onClick={() => setConfirmOpen(false)}>Cancelar</button>
              <button className="primary" type="button" onClick={createCompetition}>Confirmar</button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function RegistrationsPage() {
  const [competitions, setCompetitions] = useState([]);
  const [teams, setTeams] = useState([]);
  const [form, setForm] = useState({ competition_id: "", cpf: "", birth_date: "", team_id: "", category_id: "" });
  const [options, setOptions] = useState(null);
  const [status, setStatus] = useState("Informe competicao, CPF e nascimento");
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
    loadAllTeams().then(setTeams).catch(() => {});
  }, []);

  async function verify(nextForm = form) {
    setOptions(null);
    if (!nextForm.competition_id || normalizeCpf(nextForm.cpf).length !== 11 || !nextForm.birth_date) {
      setStatus("Informe competicao, CPF e nascimento");
      return;
    }
    try {
      const data = await fetchJson(
        `/competitions/${nextForm.competition_id}/registration-options?cpf=${encodeURIComponent(normalizeCpf(nextForm.cpf))}&birth_date=${nextForm.birth_date}`,
      );
      setOptions(data);
      setStatus(`${data.age_group} | ${beltLabels[data.athlete.belt] || data.athlete.belt} | ${data.age} anos`);
      setForm((f) => ({ ...f, team_id: data.athlete.team_id ? String(data.athlete.team_id) : "", category_id: "" }));
      setMessage(["", ""]);
    } catch (error) {
      setStatus("Dados nao conferem");
      setMessage([error.message, "error"]);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (!options) {
      setMessage(["Confirme CPF e data de nascimento antes de inscrever.", "error"]);
      return;
    }
    try {
      const registration = await fetchJson(`/competitions/${form.competition_id}/registrations`, {
        method: "POST",
        body: JSON.stringify({
          cpf: form.cpf,
          birth_date: form.birth_date,
          category_id: Number(form.category_id),
        }),
      });
      setMessage([`${registration.athlete.name} inscrito em ${categoryLabel(registration.category)}.`, "success"]);
      setForm({ competition_id: form.competition_id, cpf: "", birth_date: "", team_id: "", category_id: "" });
      setOptions(null);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const athleteLabel = options
    ? `${options.athlete.name} | ${beltLabels[options.athlete.belt] || options.athlete.belt}`
    : "";

  return (
    <section className="workspace stack">
      <form className="registration registration-inline" onSubmit={submit}>
        <div className="section-heading"><h2>Inscricao em Categoria</h2><span>{status}</span></div>
        <div className="grid registration-row">
          <Select label="Competicao" value={form.competition_id} onChange={(competition_id) => {
            const next = { ...form, competition_id };
            setForm(next);
            verify(next);
          }} required options={[["", "Selecione a competicao"], ...competitions.map((item) => [String(item.id), item.name])]} />
          <Field label="CPF" value={form.cpf} onBlur={() => verify()} onChange={(cpf) => setForm({ ...form, cpf: maskCpf(cpf) })} required />
          <Field label="Data de nascimento" type="date" value={form.birth_date} onChange={(birth_date) => {
            const next = { ...form, birth_date };
            setForm(next);
            verify(next);
          }} required />
          <Field label="Atleta confirmado" value={athleteLabel} readOnly placeholder="Confirmado apos validacao" />
          <Select label="Academia" value={form.team_id} onChange={() => {}} required disabled options={[
            ["", options ? "Atleta sem academia cadastrada" : "Aguardando validacao"],
            ...teams.map((t) => [String(t.id), t.name]),
          ]} />
          <Select label="Categoria" value={form.category_id} onChange={(category_id) => setForm({ ...form, category_id })} required disabled={!options} options={[
            ["", options ? "Selecione a categoria de peso" : "Aguardando validacao"],
            ...(options?.categories || []).map((category) => [String(category.id), category.weight_class]),
          ]} />
          <div className="inline-submit">
            <button className="primary" type="submit" disabled={!options || !form.team_id}>Inscrever atleta</button>
          </div>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
    </section>
  );
}

function BracketsPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function loadCompetitionCategories(id) {
    setCompetitionId(id);
    setCategoryId("");
    setCategoryOptions([]);
    setResult(null);
    if (!id) return;
    try {
      const [registrations, savedBrackets] = await Promise.all([
        fetchJson(`/competitions/${id}/registrations`),
        fetchJson(`/competitions/${id}/brackets`),
      ]);
      const savedCategoryIds = new Set(savedBrackets.map((bracket) => String(bracket.category_id)));
      const categories = new Map();
      registrations.forEach((registration) => {
        const key = String(registration.category.id);
        if (savedCategoryIds.has(key)) return;
        const current = categories.get(key) || { category: registration.category, count: 0 };
        categories.set(key, { ...current, count: current.count + 1 });
      });
      setCategoryOptions([...categories.values()].sort((left, right) => {
        return categoryLabel(left.category).localeCompare(categoryLabel(right.category));
      }));
      setMessage(savedCategoryIds.size ? [`${savedCategoryIds.size} categoria(s) ja possuem chave salva.`, ""] : ["", ""]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  async function generateCategory(event) {
    event.preventDefault();
    try {
      const bracket = await fetchJson(`/competitions/${competitionId}/brackets`, {
        method: "POST",
        body: JSON.stringify({ category_id: Number(categoryId) }),
      });
      setResult({
        competition_id: Number(competitionId),
        generated_count: 1,
        skipped_count: 0,
        brackets: [bracket],
      });
      setMessage([`Chave ID ${bracket.id} gerada e salva com sucesso.`, "success"]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  return (
    <section className="workspace stack">
      <form className="registration bracket-generator" onSubmit={generateCategory}>
        <div className="section-heading"><h2>Gerar Chaves</h2><span>Formato IBJJF por categoria</span></div>
        <div className="grid bracket-generator-row">
          <Select label="Competicao" value={competitionId} onChange={loadCompetitionCategories} required options={[
            ["", "Selecione a competicao"],
            ...competitions.map((competition) => [String(competition.id), competition.name]),
          ]} />
          <Select label="Categoria" value={categoryId} onChange={setCategoryId} required disabled={!competitionId || !categoryOptions.length} options={[
            ["", categoryOptions.length ? "Selecione a categoria" : "Nenhuma categoria com atletas"],
            ...categoryOptions.map((item) => [
              String(item.category.id),
              `${categoryLabel(item.category)} (${item.count})`,
            ]),
          ]} />
          <div className="inline-submit">
            <button className="primary" type="submit" disabled={!competitionId || !categoryId}>Gerar categoria</button>
          </div>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {result && (
        <section className="registration bracket-result">
          <div className="section-heading">
            <h2>Chaves Geradas</h2>
            <span>{result.generated_count} chave(s) gerada(s) e salva(s)</span>
          </div>
          <div className="landscape-scroll" aria-label="Chaves em formato paisagem">
            <div className="ibjjf-sheets">
              {result.brackets.map((bracket) => <BracketSheet bracket={bracket} key={bracket.id} showDirectLink />)}
            </div>
          </div>
          <div className="actions">
            <a className="secondary button-link" href="/chaves/salvas">Abrir chaves salvas</a>
          </div>
        </section>
      )}
    </section>
  );
}

function SavedBracketsPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [brackets, setBrackets] = useState([]);
  const [filters, setFilters] = useState({ belt: "", age_group: "", weight_class: "" });
  const [fightPanel, setFightPanel] = useState(null);
  const [blockedFightNotice, setBlockedFightNotice] = useState("");
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function loadSavedBrackets(id) {
    setCompetitionId(id);
    setBrackets([]);
    setFilters({ belt: "", age_group: "", weight_class: "" });
    setFightPanel(null);
    if (!id) return;
    try {
      const data = await fetchJson(`/competitions/${id}/brackets`);
      setBrackets(data);
      setMessage(data.length ? [`${data.length} chave(s) salva(s) carregada(s).`, "success"] : ["Nenhuma chave salva para esta competicao.", ""]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  function updateBracket(updatedBracket) {
    setBrackets((current) => current.map((bracket) => bracket.id === updatedBracket.id ? updatedBracket : bracket));
  }

  function updateSavedResult(savedResult) {
    setFightPanel((current) => current ? { ...current, match: { ...current.match, result: savedResult } } : current);
    setBrackets((current) => current.map((bracket) => ({
      ...bracket,
      matches: bracket.matches.map((match) => match.id === savedResult.match_id ? { ...match, result: savedResult } : match),
    })));
  }

  const beltOptionsForBrackets = [...new Set(brackets.map((bracket) => bracket.category.belt))]
    .sort((left, right) => (beltLabels[left] || left).localeCompare(beltLabels[right] || right));
  const ageGroupOptionsForBrackets = [...new Set(
    brackets
      .filter((bracket) => !filters.belt || bracket.category.belt === filters.belt)
      .map((bracket) => bracket.category.age_group),
  )].sort((left, right) => left.localeCompare(right));
  const weightOptionsForBrackets = [...new Set(
    brackets
      .filter((bracket) => !filters.belt || bracket.category.belt === filters.belt)
      .filter((bracket) => !filters.age_group || bracket.category.age_group === filters.age_group)
      .map((bracket) => bracket.category.weight_class),
  )].sort((left, right) => left.localeCompare(right));
  const selectedBracket = brackets.find((bracket) => (
    bracket.category.belt === filters.belt
    && bracket.category.age_group === filters.age_group
    && bracket.category.weight_class === filters.weight_class
  ));

  return (
    <section className="workspace stack">
      <form className="registration bracket-generator">
        <div className="section-heading"><h2>Chaves Salvas</h2><span>Selecione faixa, idade e peso</span></div>
        <div className="grid bracket-generator-row">
          <Select label="Competicao" value={competitionId} onChange={loadSavedBrackets} required options={[
            ["", "Selecione a competicao"],
            ...competitions.map((competition) => [String(competition.id), competition.name]),
          ]} />
          <Select label="Faixa" value={filters.belt} onChange={(belt) => setFilters({ belt, age_group: "", weight_class: "" })} disabled={!brackets.length} options={[
            ["", brackets.length ? "Selecione a faixa" : "Selecione a competicao"],
            ...beltOptionsForBrackets.map((belt) => [belt, beltLabels[belt] || belt]),
          ]} />
          <Select label="Categoria de idade" value={filters.age_group} onChange={(age_group) => setFilters({ ...filters, age_group, weight_class: "" })} disabled={!filters.belt} options={[
            ["", filters.belt ? "Selecione a idade" : "Selecione a faixa"],
            ...ageGroupOptionsForBrackets.map((ageGroup) => [ageGroup, ageGroup]),
          ]} />
          <Select label="Categoria de peso" value={filters.weight_class} onChange={(weight_class) => setFilters({ ...filters, weight_class })} disabled={!filters.age_group} options={[
            ["", filters.age_group ? "Selecione o peso" : "Selecione a idade"],
            ...weightOptionsForBrackets.map((weightClass) => [weightClass, weightClass]),
          ]} />
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {!!brackets.length && (
        <section className="panel saved-brackets-panel">
          <div className="section-heading">
            <h2>Consulta de Chaves</h2>
            <span>{selectedBracket ? `ID ${selectedBracket.id}` : `${brackets.length} chave(s) salva(s)`}</span>
          </div>
          {selectedBracket ? (
            <div className="checkin-table-wrap">
              <table className="checkin-table saved-brackets-table">
                <thead><tr><th>ID</th><th>Faixa</th><th>Idade</th><th>Peso</th><th>Atletas</th><th>Lutas</th><th>Link</th></tr></thead>
                <tbody>
                  <tr>
                    <td data-label="ID">#{selectedBracket.id}</td>
                    <td data-label="Faixa">{beltLabels[selectedBracket.category.belt] || selectedBracket.category.belt}</td>
                    <td data-label="Idade">{selectedBracket.category.age_group}</td>
                    <td data-label="Peso">{selectedBracket.category.weight_class}</td>
                    <td data-label="Atletas">{selectedBracket.entries.filter((entry) => entry.athlete).length}</td>
                    <td data-label="Lutas">{selectedBracket.matches.length}</td>
                    <td data-label="Link"><a href={`/chaves/${selectedBracket.id}`}>Abrir URL</a></td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">Selecione a faixa, a categoria de idade e a categoria de peso para exibir a chave.</div>
          )}
        </section>
      )}
      {selectedBracket && (
        <section className="registration bracket-result">
          <div className="section-heading">
            <h2>Exibicao da Chave</h2>
            <span>ID {selectedBracket.id} | {categoryLabel(selectedBracket.category)}</span>
          </div>
          <div className="landscape-scroll" aria-label="Chaves salvas em formato paisagem">
            <div className="ibjjf-sheets">
              <BracketSheet bracket={selectedBracket} showDirectLink onOpenFight={(match, matchNumber) => setFightPanel({ bracket: selectedBracket, match, matchNumber })} onBlockedFight={setBlockedFightNotice} />
            </div>
          </div>
        </section>
      )}
      {blockedFightNotice && (
        <div className="modal-backdrop fight-modal-backdrop" role="alertdialog" aria-modal="true">
          <section className="fight-confirm">
            <h2>Luta ja finalizada</h2>
            <p>{blockedFightNotice}</p>
            <div className="actions">
              <button className="primary" type="button" onClick={() => setBlockedFightNotice("")}>OK</button>
            </div>
          </section>
        </div>
      )}
      {fightPanel && <FightPanel data={fightPanel} onClose={() => setFightPanel(null)} onBracketUpdated={updateBracket} onResultSaved={updateSavedResult} />}
    </section>
  );
}

function SchedulePage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [schedule, setSchedule] = useState(null);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function loadSchedule(id) {
    setCompetitionId(id);
    setSchedule(null);
    if (!id) return;
    try {
      const data = await fetchJson(`/competitions/${id}/schedule`);
      setSchedule(data);
      setMessage(data.categories.length ? ["", ""] : ["Nenhuma chave agendada para esta competicao.", ""]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const categoriesByDay = useMemo(() => {
    const grouped = new Map();
    (schedule?.categories || []).forEach((item) => {
      if (!grouped.has(item.day_number)) grouped.set(item.day_number, []);
      grouped.get(item.day_number).push(item);
    });
    return [...grouped.entries()].sort(([left], [right]) => left - right);
  }, [schedule]);

  const rowsBySex = (rows, sex) => rows
    .filter((item) => item.sex === sex)
    .sort((left, right) => new Date(left.start_time) - new Date(right.start_time));

  return (
    <section className="workspace stack schedule-workspace">
      <form className="registration bracket-generator">
        <div className="section-heading"><h2>Cronograma</h2><span>Horarios estimados por categoria</span></div>
        <div className="grid bracket-generator-row">
          <Select label="Competicao" value={competitionId} onChange={loadSchedule} required options={[
            ["", "Selecione a competicao"],
            ...competitions.map((competition) => [String(competition.id), competition.name]),
          ]} />
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {schedule && (
        <section className="schedule-page">
          <header className="schedule-header">
            <h2>SCHEDULE</h2>
            <p>{schedule.competition.name}</p>
          </header>
          <div className="schedule-copy">
            <p>Este e o cronograma com os <strong>horarios estimados de inicio de cada categoria</strong>.</p>
            <p>Os atletas devem estar no ginasio prontos com antecedencia minima de <strong>uma hora</strong>.</p>
            <p>A luta pode iniciar antes ou depois do horario previsto conforme o andamento dos MATS.</p>
          </div>
          {categoriesByDay.map(([dayNumber, rows]) => {
            const first = rows[0];
            return (
              <section className="schedule-day" key={dayNumber}>
                <div className="schedule-day-band">
                  <strong>{formatScheduleDay(first.start_time)}</strong>
                  <span>START TIME: {formatScheduleTime(first.start_time)}</span>
                </div>
                <div className="schedule-columns">
                  {["male", "female"].map((sex) => (
                    <section className="schedule-sex-column" key={sex}>
                      <h3>{sex === "male" ? "MALE" : "FEMALE"}</h3>
                      <div className="schedule-list">
                        {rowsBySex(rows, sex).map((item) => (
                          <a className="schedule-row" href={`/chaves/${item.bracket_id}`} key={item.bracket_id}>
                            <span>{categoryLabel(item.category)}</span>
                            <strong>{formatScheduleTime(item.start_time)}, MAT {item.mat_number}</strong>
                          </a>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </section>
            );
          })}
        </section>
      )}
    </section>
  );
}

function BracketByIdPage({ bracketId }) {
  const [bracket, setBracket] = useState(null);
  const [fightPanel, setFightPanel] = useState(null);
  const [blockedFightNotice, setBlockedFightNotice] = useState("");
  const [message, setMessage] = useState(["Carregando chave...", ""]);

  useEffect(() => {
    fetchJson(`/competitions/brackets/${bracketId}`)
      .then((data) => {
        setBracket(data);
        setMessage(["", ""]);
      })
      .catch((error) => setMessage([error.message, "error"]));
  }, [bracketId]);

  function updateSavedResult(savedResult) {
    setFightPanel((current) => current ? { ...current, match: { ...current.match, result: savedResult } } : current);
    setBracket((current) => current ? {
      ...current,
      matches: current.matches.map((match) => match.id === savedResult.match_id ? { ...match, result: savedResult } : match),
    } : current);
  }

  return (
    <section className="workspace stack">
      <section className="registration bracket-result">
        <div className="section-heading">
          <h2>Consulta da Chave</h2>
          <span>{bracket ? `ID ${bracket.id} | ${categoryLabel(bracket.category)}` : `ID ${bracketId}`}</span>
        </div>
        <Message text={message[0]} type={message[1]} />
        {bracket && (
          <>
            <div className="landscape-scroll" aria-label="Chave em formato paisagem">
              <div className="ibjjf-sheets">
                <BracketSheet bracket={bracket} showDirectLink onOpenFight={(match, matchNumber) => setFightPanel({ bracket, match, matchNumber })} onBlockedFight={setBlockedFightNotice} />
              </div>
            </div>
            <div className="actions">
              <a className="secondary button-link" href="/chaves/salvas">Consultar outras chaves</a>
            </div>
          </>
        )}
      </section>
      {blockedFightNotice && (
        <div className="modal-backdrop fight-modal-backdrop" role="alertdialog" aria-modal="true">
          <section className="fight-confirm">
            <h2>Luta ja finalizada</h2>
            <p>{blockedFightNotice}</p>
            <div className="actions">
              <button className="primary" type="button" onClick={() => setBlockedFightNotice("")}>OK</button>
            </div>
          </section>
        </div>
      )}
      {fightPanel && <FightPanel data={fightPanel} onClose={() => setFightPanel(null)} onBracketUpdated={setBracket} onResultSaved={updateSavedResult} />}
    </section>
  );
}

function BracketSheet({ bracket, onOpenFight, onBlockedFight, showDirectLink = false }) {
  const sheetRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const summary = [
    `${bracket.bracket_size} posicoes`,
    `${bracket.bye_count} byes`,
    `${bracket.rounds} rodadas`,
  ].join(" | ");

  async function exportPdf() {
    if (!sheetRef.current) return;
    setExporting(true);
    setExportError("");
    try {
      await exportBracketPdf(sheetRef.current, bracket);
    } catch (error) {
      setExportError(error.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="ibjjf-sheet-wrap">
      <section className="ibjjf-sheet" ref={sheetRef}>
        <div className="ibjjf-sheet-header">
          <p className="ibjjf-kicker">FJJPE</p>
          <h2>{categoryLabel(bracket.category)}</h2>
          <span>ID {bracket.id} | {summary}</span>
        </div>
        <div className="ibjjf-board">
          <CompactBracket bracket={bracket} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
        </div>
      </section>
      <div className="ibjjf-sheet-actions">
        {showDirectLink && <a className="secondary button-link" href={`/chaves/${bracket.id}`}>URL da chave</a>}
        <button className="secondary" type="button" onClick={exportPdf} disabled={exporting}>
          {exporting ? "Exportando PDF" : "Exportar PDF"}
        </button>
        {exportError && <span className="pdf-error">{exportError}</span>}
      </div>
    </section>
  );
}

function CompactBracket({ bracket, onOpenFight, onBlockedFight }) {
  const halfSize = bracket.bracket_size / 2;
  const sideA = bracket.matches.filter((match) => match.round_number < bracket.rounds && match.position_end <= halfSize);
  const sideB = bracket.matches.filter((match) => match.round_number < bracket.rounds && match.position_start > halfSize);
  const finalMatch = bracket.matches.find((match) => match.round_number === bracket.rounds);
  const matchNumbers = bracketMatchNumbers(sideA, sideB, finalMatch);
  return (
    <div className="ibjjf-compact-board">
      <BracketSide title="Lado A" subtitle={`Posicoes 1-${halfSize}`} matches={sideA} allMatches={bracket.matches} totalRounds={bracket.rounds} direction="left" matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
      <FinalSection match={finalMatch} title="Final" allMatches={bracket.matches} matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
      <BracketSide title="Lado B" subtitle={`Posicoes ${halfSize + 1}-${bracket.bracket_size}`} matches={sideB} allMatches={bracket.matches} totalRounds={bracket.rounds} direction="right" matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
    </div>
  );
}

function SplitBracket({ bracket, onOpenFight, onBlockedFight }) {
  return (
    <>
      <BracketHalf bracket={bracket} index={1} start={1} end={bracket.bracket_size / 2} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
      <BracketHalf bracket={bracket} index={2} start={bracket.bracket_size / 2 + 1} end={bracket.bracket_size} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
      <section className="ibjjf-finals-block">
        <div className="ibjjf-bracket-block-title">FINALS</div>
        <div className="ibjjf-finals-center">
          <FinalSection match={bracket.matches.find((match) => match.round_number === bracket.rounds)} title="Final" onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
        </div>
      </section>
    </>
  );
}

function BracketHalf({ bracket, index, start, end, onOpenFight, onBlockedFight }) {
  const blockRef = useRef(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const middle = start + (end - start + 1) / 2 - 1;
  const blockFinalRound = bracket.rounds - 1;
  const left = bracket.matches.filter((match) => match.round_number < blockFinalRound && match.position_start >= start && match.position_end <= middle);
  const right = bracket.matches.filter((match) => match.round_number < blockFinalRound && match.position_start > middle && match.position_end <= end);
  const finalMatch = bracket.matches.find((match) => match.round_number === blockFinalRound && match.position_start >= start && match.position_end <= end);
  const matchNumbers = bracketMatchNumbers(left, right, finalMatch);

  async function exportPdf() {
    if (!blockRef.current) return;
    setExporting(true);
    setExportError("");
    try {
      await exportBracketPdf(blockRef.current, bracket, `bracket-${index}`);
    } catch (error) {
      setExportError(error.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="ibjjf-bracket-block-wrap">
      <section className="ibjjf-bracket-block" ref={blockRef}>
        <div className="ibjjf-bracket-block-title">BRACKET {index}/2</div>
        <div className="ibjjf-compact-board">
          <BracketSide title={`Lado ${index}A`} subtitle={`Posicoes ${start}-${middle}`} matches={left} totalRounds={bracket.rounds} direction="left" matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
          <FinalSection match={finalMatch} title="Final do bracket" matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
          <BracketSide title={`Lado ${index}B`} subtitle={`Posicoes ${middle + 1}-${end}`} matches={right} totalRounds={bracket.rounds} direction="right" matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
        </div>
      </section>
      <div className="ibjjf-sheet-actions bracket-block-actions">
        <button className="secondary" type="button" onClick={exportPdf} disabled={exporting}>
          {exporting ? `Exportando BRACKET ${index}` : `Exportar BRACKET ${index}`}
        </button>
        {exportError && <span className="pdf-error">{exportError}</span>}
      </div>
    </section>
  );
}

function bracketMatchNumbers(leftMatches, rightMatches, finalMatch) {
  const numbers = new Map();
  orderedBracketMatches(leftMatches).forEach((match, index) => {
    numbers.set(match.id, index * 2 + 1);
  });
  orderedBracketMatches(rightMatches).forEach((match, index) => {
    numbers.set(match.id, index * 2 + 2);
  });
  if (finalMatch) {
    numbers.set(finalMatch.id, leftMatches.length + rightMatches.length + 1);
  }
  return numbers;
}

function orderedBracketMatches(matches) {
  return [...matches].sort((left, right) => {
    if (left.round_number !== right.round_number) return left.round_number - right.round_number;
    return left.match_number - right.match_number;
  });
}

function BracketSide({ title, subtitle, matches, allMatches, totalRounds, direction, matchNumbers, onOpenFight, onBlockedFight }) {
  const roundsRef = useRef(null);
  const [connectors, setConnectors] = useState([]);
  const grouped = useMemo(() => {
    const map = new Map();
    matches.forEach((match) => {
      if (!map.has(match.round_number)) map.set(match.round_number, []);
      map.get(match.round_number).push(match);
    });
    return [...map.entries()].sort(([left], [right]) => direction === "right" ? right - left : left - right);
  }, [matches, direction]);

  useLayoutEffect(() => {
    function drawConnectors() {
      const root = roundsRef.current;
      if (!root) return;

      const rootBox = root.getBoundingClientRect();
      const columns = [...root.querySelectorAll(".ibjjf-round")].map((round) => {
        return [...round.querySelectorAll(".ibjjf-match")].map((match) => {
          const box = match.getBoundingClientRect();
          return {
            left: box.left - rootBox.left,
            right: box.right - rootBox.left,
            y: box.top - rootBox.top + box.height / 2,
          };
        });
      });
      const paths = [];

      for (let columnIndex = 0; columnIndex < columns.length - 1; columnIndex += 1) {
        const current = columns[columnIndex];
        const next = columns[columnIndex + 1];
        if (!current.length || !next.length) continue;

        if (current.length >= next.length) {
          current.forEach((source, sourceIndex) => {
            const target = next[Math.min(Math.floor(sourceIndex / 2), next.length - 1)];
            paths.push(buildConnectorPath(source, target, direction));
          });
        } else {
          next.forEach((target, targetIndex) => {
            const source = current[Math.min(Math.floor(targetIndex / 2), current.length - 1)];
            paths.push(buildConnectorPath(source, target, direction));
          });
        }
      }

      setConnectors(paths);
    }

    drawConnectors();
    window.addEventListener("resize", drawConnectors);
    return () => window.removeEventListener("resize", drawConnectors);
  }, [grouped, direction]);

  return (
    <section className={`ibjjf-side ${direction}`}>
      <div className="ibjjf-side-header"><strong>{title}</strong><span>{subtitle}</span></div>
      <div className="ibjjf-rounds" ref={roundsRef}>
        <svg className="ibjjf-connectors" aria-hidden="true">
          {connectors.map((path, index) => <path d={path} key={`${path}-${index}`} />)}
        </svg>
        {grouped.map(([roundNumber, roundMatches]) => (
          <section className={`ibjjf-round ${direction}`} key={roundNumber}>
            <div className="ibjjf-round-title">
              <strong>{roundLabel(roundNumber, totalRounds)}</strong>
              <span>{roundMatches.length} luta(s)</span>
            </div>
            <div className="ibjjf-match-list">
              {roundMatches.sort((a, b) => a.match_number - b.match_number).map((match) => (
                <MatchCard match={match} allMatches={allMatches} direction={direction} key={match.id} matchNumber={matchNumbers?.get(match.id)} matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function buildConnectorPath(source, target, direction) {
  const sourceX = direction === "right" ? source.left : source.right;
  const targetX = direction === "right" ? target.right : target.left;
  const middleX = sourceX + (targetX - sourceX) / 2;
  return `M ${sourceX} ${source.y} H ${middleX} V ${target.y} H ${targetX}`;
}

function FinalSection({ match, title, allMatches, matchNumbers, onOpenFight, onBlockedFight }) {
  return (
    <section className="ibjjf-final-section">
      <div className="ibjjf-side-header final-header"><strong>{title}</strong></div>
      <div className="ibjjf-final-match">{match && <MatchCard match={match} allMatches={allMatches} direction="final" matchNumber={matchNumbers?.get(match.id)} matchNumbers={matchNumbers} onOpenFight={onOpenFight} onBlockedFight={onBlockedFight} />}</div>
    </section>
  );
}

function roundLabel(roundNumber, totalRounds) {
  const roundsFromFinal = totalRounds - roundNumber;
  if (roundsFromFinal === 0) return "Final";
  if (roundsFromFinal === 1) return "Semifinal";
  if (roundsFromFinal === 2) return "Quartas";
  return `Rodada ${roundNumber}`;
}

function originMatchForSlot(match, allMatches, side) {
  if (!allMatches || match.round_number <= 1) return null;
  const middle = Math.floor((match.position_start + match.position_end) / 2);
  const start = side === "a" ? match.position_start : middle + 1;
  const end = side === "a" ? middle : match.position_end;
  return allMatches.find((item) => (
    item.round_number === match.round_number - 1
    && item.position_start === start
    && item.position_end === end
  )) || null;
}

function placeholderAthlete(match, allMatches, matchNumbers, side) {
  const origin = originMatchForSlot(match, allMatches, side);
  if (origin) {
    const originNumber = matchNumbers?.get(origin.id) || origin.match_number;
    return { name: `Vencedor da luta ${originNumber}`, team: { name: "-" }, isPlaceholder: true };
  }
  return {
    name: match.status === "bye" ? "BYE" : "Vencedor da luta",
    team: { name: "-" },
    isPlaceholder: true,
  };
}

function MatchCard({ match, allMatches, direction, matchNumber, matchNumbers, onOpenFight, onBlockedFight }) {
  const left = match.athlete_a || placeholderAthlete(match, allMatches, matchNumbers, "a");
  const right = match.athlete_b || placeholderAthlete(match, allMatches, matchNumbers, "b");
  const athleteName = (athlete) => `${athlete.name}${athlete.is_ranked ? " *" : ""}`;
  const checkinClass = (athlete) => (athlete.checkin_status || "No Show").toLowerCase().replace(/\s+/g, "-");
  const isFinalized = Boolean(match.result?.finalized);
  const winnerId = match.result?.winner_id;
  const resultMethodKey = (match.result?.finish_method || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, "-");
  const canOpenFight = Boolean(onOpenFight) && !isFinalized && left.id && right.id && left.checkin_status === "Checked" && right.checkin_status === "Checked";
  const canInteract = canOpenFight || isFinalized;
  const resultSide = (athlete) => {
    if (!isFinalized || !athlete.id || !winnerId) return "";
    return athlete.id === winnerId ? "result-winner" : "result-loser";
  };
  const resultBadge = (athlete) => {
    const side = resultSide(athlete);
    if (side !== "result-winner") return null;
    return (
      <span
        className={`match-result-dot ${side} ${resultMethodKey}`}
        title={`Vitoria por ${match.result.finish_method}`}
        aria-label={`Vitoria por ${match.result.finish_method}`}
      />
    );
  };
  const athleteLine = (athlete) => (
    <span className={`ibjjf-athlete-line ${resultSide(athlete)}`.trim()}>
      {athlete.id && !athlete.isPlaceholder && <span className={`bracket-check-status ${checkinClass(athlete)}`} title={athlete.checkin_status || "No Show"} />}
      <strong>{athleteName(athlete)}</strong>
    </span>
  );
  const teamLine = (athlete) => (
    <span className="ibjjf-team-line">
      <small>{athlete.team?.name || ""}</small>
      {resultBadge(athlete)}
    </span>
  );
  const displayedMatchNumber = matchNumber || match.match_number;
  const matchLabel = match.status === "bye"
    ? `FIGHT ${displayedMatchNumber} | BYE`
    : `FIGHT ${displayedMatchNumber}`;
  const openFight = () => {
    if (isFinalized) {
      onBlockedFight?.("Luta ja finalizada. Nao e possivel reabrir ou alterar o resultado.");
      return;
    }
    if (canOpenFight) onOpenFight?.(match, displayedMatchNumber);
  };
  return (
    <article className={`ibjjf-match ${direction} ${canOpenFight ? "clickable" : isFinalized ? "finalized" : "locked"}`.trim()} role={canInteract ? "button" : undefined} tabIndex={canInteract ? "0" : undefined} onClick={openFight} onKeyDown={(event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openFight();
      }
    }}>
      <div className="ibjjf-match-meta"><strong>{matchLabel}</strong><span>Mat {match.schedule?.mat_number || "-"}</span></div>
      <div className="ibjjf-slot winner">
        <span className="ibjjf-position">{match.position_start}</span>
        <div>{athleteLine(left)}{teamLine(left)}</div>
      </div>
      <div className="ibjjf-slot">
        <span className="ibjjf-position">{match.position_end}</span>
        <div>{athleteLine(right)}{teamLine(right)}</div>
      </div>
      {match.schedule && (
        <div className="ibjjf-match-schedule">
          Dia {match.schedule.day_number} | {formatScheduleDay(match.schedule.scheduled_start)} {formatScheduleTime(match.schedule.scheduled_start)} | MAT {match.schedule.mat_number}
        </div>
      )}
    </article>
  );
}

function fightDurationSeconds(category) {
  const belt = category?.belt;
  const ageGroup = category?.age_group || "";
  if (ageGroup === "Adult") {
    return {
      white: 5,
      blue: 6,
      purple: 7,
      brown: 8,
      black: 10,
    }[belt] * 60 || 5 * 60;
  }
  if (ageGroup === "Juvenile") return 5 * 60;
  if (ageGroup === "Master 1") {
    return ["purple", "brown", "black"].includes(belt) ? 6 * 60 : 5 * 60;
  }
  if (ageGroup.startsWith("Master")) return 5 * 60;
  return 5 * 60;
}

function formatFightTime(seconds) {
  const safeSeconds = Math.max(0, seconds);
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function emptyFightScores() {
  return {
    a: { points: 0, advantages: 0, penalties: 0 },
    b: { points: 0, advantages: 0, penalties: 0 },
  };
}

function resultToFightScores(result) {
  if (!result) return emptyFightScores();
  return {
    a: {
      points: result.athlete_a_points,
      advantages: result.athlete_a_advantages,
      penalties: result.athlete_a_penalties,
    },
    b: {
      points: result.athlete_b_points,
      advantages: result.athlete_b_advantages,
      penalties: result.athlete_b_penalties,
    },
  };
}

function fightScoreWinner(scores, athleteA, athleteB) {
  const checks = [
    [scores.a.points, scores.b.points, true],
    [scores.a.advantages, scores.b.advantages, true],
    [scores.a.penalties, scores.b.penalties, false],
  ];
  for (const [left, right, higherWins] of checks) {
    if (left === right) continue;
    if (higherWins) return left > right ? athleteA : athleteB;
    return left < right ? athleteA : athleteB;
  }
  return null;
}

function FightPanel({ data, onClose, onResultSaved, onBracketUpdated }) {
  const { bracket, match, matchNumber } = data;
  const duration = fightDurationSeconds(bracket.category);
  const [timeLeft, setTimeLeft] = useState(duration);
  const [running, setRunning] = useState(false);
  const [scores, setScores] = useState(() => resultToFightScores(match.result));
  const [savedResult, setSavedResult] = useState(match.result || null);
  const [saveMessage, setSaveMessage] = useState("");
  const [pendingFinish, setPendingFinish] = useState(null);
  const athleteA = match.athlete_a || { name: "A definir", team: { name: "" } };
  const athleteB = match.athlete_b || { name: "A definir", team: { name: "" } };
  const categoryText = [
    bracket.category.age_group,
    beltLabels[bracket.category.belt] || bracket.category.belt,
    bracket.category.weight_class,
  ].join(" | ");

  useEffect(() => {
    if (!running || timeLeft <= 0) return undefined;
    const timer = window.setInterval(() => {
      setTimeLeft((current) => {
        if (current <= 1) {
          setRunning(false);
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, timeLeft]);

  function addScore(side, field) {
    adjustScore(side, field, 1);
  }

  async function persistScores(nextScores, finish = {}) {
    const payload = {
      athlete_a_points: nextScores.a.points,
      athlete_a_advantages: nextScores.a.advantages,
      athlete_a_penalties: nextScores.a.penalties,
      athlete_b_points: nextScores.b.points,
      athlete_b_advantages: nextScores.b.advantages,
      athlete_b_penalties: nextScores.b.penalties,
      finalized: finish.finalized ?? savedResult?.finalized ?? false,
      finish_method: finish.finish_method ?? savedResult?.finish_method ?? null,
      winner_id: finish.winner_id ?? savedResult?.winner_id ?? null,
    };
    if (!payload.finalized) {
      payload.finish_method = null;
      payload.winner_id = null;
    }
    const result = await fetchJson(`/competitions/${bracket.competition_id}/matches/${match.id}/result`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    setSavedResult(result);
    onResultSaved?.(result);
    setSaveMessage(result.finalized ? `Resultado salvo: ${result.finish_method}` : "Placar salvo");
    if (result.finalized) {
      const updatedBracket = await fetchJson(`/competitions/brackets/${bracket.id}`);
      onBracketUpdated?.(updatedBracket);
      const updatedMatch = updatedBracket.matches.find((item) => item.id === match.id);
      if (updatedMatch) {
        setSavedResult(updatedMatch.result || result);
      }
      onClose?.();
    }
    return result;
  }

  async function adjustScore(side, field, delta) {
    const nextScores = {
      ...scores,
      [side]: {
        ...scores[side],
        [field]: Math.max(0, scores[side][field] + delta),
      },
    };
    setScores(nextScores);
    try {
      await persistScores(nextScores);
    } catch (error) {
      setSaveMessage(error.message);
    }
  }

  function finishByTime() {
    const winner = fightScoreWinner(scores, athleteA, athleteB);
    if (!winner) {
      setSaveMessage("Empate total: pontos, vantagens e punicoes iguais.");
      return;
    }
    setPendingFinish({
      title: "Encerrar luta por tempo?",
      body: `Deseja encerrar a luta por tempo? Vencedor pela pontuacao: ${winner.name}.`,
      winnerName: winner.name,
      finish: { finalized: true, finish_method: "Pontos", winner_id: null },
    });
  }

  function finishBySubmission(side) {
    const winner = side === "a" ? athleteA : athleteB;
    setPendingFinish({
      title: "Encerrar por finalizacao?",
      body: `Deseja encerrar a luta por finalizacao de ${winner.name}?`,
      winnerName: winner.name,
      finish: { finalized: true, finish_method: "Finalizacao", winner_id: winner.id },
    });
  }

  function disqualify(side) {
    const disqualified = side === "a" ? athleteA : athleteB;
    const winner = side === "a" ? athleteB : athleteA;
    setPendingFinish({
      title: "Encerrar por desclassificacao?",
      body: `Deseja encerrar a luta por desclassificacao de ${disqualified.name}? Vencedor: ${winner.name}.`,
      winnerName: winner.name,
      finish: { finalized: true, finish_method: "Desclassificacao do oponente", winner_id: winner.id },
    });
  }

  async function confirmFinish() {
    if (!pendingFinish) return;
    try {
      await persistScores(scores, pendingFinish.finish);
      setPendingFinish(null);
    } catch (error) {
      setSaveMessage(error.message);
    }
  }

  return (
    <div className="modal-backdrop fight-modal-backdrop" role="dialog" aria-modal="true">
      <section className="fight-panel">
        <button className="fight-close" type="button" onClick={onClose} aria-label="Fechar painel de luta">x</button>
        <div className="fight-rows">
          <FightAthleteRow athlete={athleteA} score={scores.a} active onScore={(field) => addScore("a", field)} onAdjust={(field, delta) => adjustScore("a", field, delta)} onSubmission={() => finishBySubmission("a")} onDisqualification={() => disqualify("a")} />
          <FightAthleteRow athlete={athleteB} score={scores.b} onScore={(field) => addScore("b", field)} onAdjust={(field, delta) => adjustScore("b", field, delta)} onSubmission={() => finishBySubmission("b")} onDisqualification={() => disqualify("b")} />
        </div>
        <footer className="fight-footer">
          <div className="fight-info">
            <strong>{categoryText}</strong>
            <span>Luta {matchNumber} {match.status === "bye" ? "| BYE" : ""}</span>
            {saveMessage && <small>{saveMessage}</small>}
            <div className="fight-actions">
              <button className="primary" type="button" onClick={finishByTime}>Finalizar por tempo</button>
              <button className="secondary" type="button" onClick={() => {
                setRunning(false);
                setTimeLeft(duration);
              }}>Reset tempo</button>
            </div>
          </div>
          <button className={`fight-clock ${running ? "running" : ""}`} type="button" onClick={() => setRunning((current) => !current)}>
            {formatFightTime(timeLeft)}
          </button>
        </footer>
        {pendingFinish && (
          <div className="fight-confirm-backdrop" role="alertdialog" aria-modal="true">
            <section className="fight-confirm">
              <h2>{pendingFinish.title}</h2>
              <p>{pendingFinish.body}</p>
              <strong>Vencedor: {pendingFinish.winnerName}</strong>
              <div className="actions">
                <button className="secondary" type="button" onClick={() => setPendingFinish(null)}>Cancelar</button>
                <button className="primary" type="button" onClick={confirmFinish}>Confirmar</button>
              </div>
            </section>
          </div>
        )}
      </section>
    </div>
  );
}

function FightAthleteRow({ athlete, score, active = false, onScore, onAdjust, onSubmission, onDisqualification }) {
  return (
    <section className={`fight-athlete-row ${active ? "active" : ""}`.trim()}>
      <div className="fight-athlete-info">
        <div className="fight-athlete-name"><strong>{athlete.name}</strong></div>
        <span>{athlete.team?.name || ""}</span>
        <div className="fight-finish-actions">
          <button className="primary" type="button" onClick={onSubmission}>Finalizacao</button>
          <button className="danger-button" type="button" onClick={onDisqualification}>Desclassificacao</button>
        </div>
      </div>
      <FightScoreBox className="points" label="pontos" value={score.points} onScore={() => onScore("points")} onAdjust={(delta) => onAdjust("points", delta)} athleteName={athlete.name} />
      <FightScoreBox className="advantages" label="vantagens" value={score.advantages} onScore={() => onScore("advantages")} onAdjust={(delta) => onAdjust("advantages", delta)} athleteName={athlete.name} />
      <FightScoreBox className="penalties" label="punicoes" value={score.penalties} onScore={() => onScore("penalties")} onAdjust={(delta) => onAdjust("penalties", delta)} athleteName={athlete.name} />
    </section>
  );
}

function FightScoreBox({ className, label, value, onScore, onAdjust, athleteName }) {
  return (
    <div className={`fight-score-box ${className}`}>
      <button className={`fight-score ${className}`} type="button" onClick={onScore} aria-label={`Adicionar ${label} para ${athleteName}`}>
        {value}
      </button>
      <div className="fight-score-controls">
        <button type="button" onClick={() => onAdjust(1)} aria-label={`Adicionar ${label}`}>+</button>
        <button type="button" onClick={() => onAdjust(-1)} aria-label={`Remover ${label}`}>-</button>
      </div>
    </div>
  );
}

function RankingPage() {
  const emptyForm = {
    belt: "",
    age_group: "",
    athlete_id: "",
    points: "",
    competition_name: "",
  };
  const [form, setForm] = useState(emptyForm);
  const [options, setOptions] = useState({ belts: [], age_groups: [], athletes: [] });
  const [competitions, setCompetitions] = useState([]);
  const [standings, setStandings] = useState({ groups: [], total_ranked: 0 });
  const [message, setMessage] = useState(["", ""]);

  async function loadOptions(nextForm = form) {
    const params = new URLSearchParams();
    if (nextForm.belt) params.set("belt", nextForm.belt);
    if (nextForm.age_group) params.set("age_group", nextForm.age_group);
    const data = await fetchJson(`/ranking/options?${params.toString()}`);
    setOptions(data);
  }

  async function loadStandings() {
    setStandings(await fetchJson("/ranking/standings"));
  }

  useEffect(() => {
    loadOptions().catch((error) => setMessage([error.message, "error"]));
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
    loadStandings().catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function submit(event) {
    event.preventDefault();
    try {
      const entry = await fetchJson("/ranking", {
        method: "POST",
        body: JSON.stringify({
          athlete_id: Number(form.athlete_id),
          belt: form.belt,
          age_group: form.age_group,
          points: Number(form.points),
          competition_name: form.competition_name,
        }),
      });
      setMessage([`${entry.points} ponto(s) lancados para ${entry.athlete.name}.`, "success"]);
      setForm({ ...emptyForm, belt: form.belt, age_group: form.age_group });
      await loadOptions({ ...emptyForm, belt: form.belt, age_group: form.age_group });
      await loadStandings();
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const selectedAthlete = options.athletes.find((athlete) => String(athlete.id) === form.athlete_id);

  return (
    <section className="workspace stack">
      <form className="registration registration-inline ranking-form" onSubmit={submit}>
        <div className="section-heading">
          <h2>Pontuacao de Ranking</h2>
          <span>{selectedAthlete ? selectedAthlete.team_name : "Selecione faixa, categoria e atleta"}</span>
        </div>
        <div className="grid ranking-row">
          <Select label="Faixa" value={form.belt} onChange={(belt) => {
            const next = { ...form, belt, age_group: "", athlete_id: "" };
            setForm(next);
            loadOptions(next).catch((error) => setMessage([error.message, "error"]));
          }} required options={[
            ["", "Selecione a faixa"],
            ...options.belts.map((belt) => [belt, beltLabels[belt] || belt]),
          ]} />
          <Select label="Categoria por idade" value={form.age_group} onChange={(age_group) => {
            const next = { ...form, age_group, athlete_id: "" };
            setForm(next);
            loadOptions(next).catch((error) => setMessage([error.message, "error"]));
          }} required disabled={!form.belt} options={[
            ["", form.belt ? "Selecione a categoria" : "Selecione a faixa primeiro"],
            ...options.age_groups.map((ageGroup) => [ageGroup, ageGroup]),
          ]} />
          <Select label="Atleta" value={form.athlete_id} onChange={(athlete_id) => setForm({ ...form, athlete_id })} required disabled={!form.age_group} options={[
            ["", form.age_group ? "Selecione o atleta" : "Selecione a categoria primeiro"],
            ...options.athletes.map((athlete) => [String(athlete.id), `${athlete.name} | ${athlete.team_name}`]),
          ]} />
          <Field label="Pontos" type="number" min="1" step="1" value={form.points} onChange={(points) => setForm({ ...form, points })} required />
          <Select label="Competicao" value={form.competition_name} onChange={(competition_name) => setForm({ ...form, competition_name })} required options={[
            ["", "Selecione a competicao"],
            ...competitions.map((competition) => [competition.name, competition.name]),
          ]} />
          <div className="inline-submit">
            <button className="primary" type="submit">Lancar pontos</button>
          </div>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>

      <section className="panel ranking-panel">
        <div className="section-heading">
          <h2>Consulta de Ranking</h2>
          <span>{standings.total_ranked} atleta(s) ranqueado(s)</span>
        </div>
        <div className="checkin-groups">
          {standings.groups.map((group) => (
            <section className="checkin-group" key={`${group.belt}-${group.age_group}`}>
              <div className="checkin-group-heading">
                <h2>{[beltLabels[group.belt] || group.belt, group.age_group].join(" | ")}</h2>
                <span>{group.athletes.length} atleta(s)</span>
              </div>
              <div className="checkin-table-wrap">
                <table className="checkin-table ranking-table">
                  <thead><tr><th>Posicao</th><th>Atleta</th><th>Equipe</th><th>Pontos</th><th>Lancamentos</th></tr></thead>
                  <tbody>
                    {group.athletes.map((item) => (
                      <tr key={`${group.belt}-${group.age_group}-${item.athlete_id}`}>
                        <td data-label="Posicao">#{item.position}</td>
                        <td data-label="Atleta">{item.athlete.name}</td>
                        <td data-label="Equipe">{item.athlete.team?.name}</td>
                        <td data-label="Pontos">{item.total_points}</td>
                        <td data-label="Lancamentos">{item.entry_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
        {!standings.groups.length && <div className="empty">Nenhum ponto de ranking lancado.</div>}
      </section>
    </section>
  );
}

function WeighinPage() {
  const emptyForm = { competition_id: "", cpf: "", checked_weight: "" };
  const [competitions, setCompetitions] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [lookup, setLookup] = useState(null);
  const [message, setMessage] = useState(["", ""]);
  const [warningOpen, setWarningOpen] = useState(false);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function findAthlete(nextForm = form) {
    setLookup(null);
    if (!nextForm.competition_id || normalizeCpf(nextForm.cpf).length !== 11) return;
    try {
      const data = await fetchJson(
        `/competitions/${nextForm.competition_id}/checkin-options?cpf=${encodeURIComponent(normalizeCpf(nextForm.cpf))}`,
      );
      setLookup(data);
      setForm({
        ...nextForm,
        checked_weight: data.checkin?.checked_weight ? String(data.checkin.checked_weight) : "",
      });
      setMessage(data.checkin
        ? ["Este atleta ja foi pesado nesta competicao. Nova pesagem bloqueada.", "error"]
        : ["Atleta localizado para pesagem.", "success"]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  function isOverweight() {
    if (!lookup?.max_weight_kg || !form.checked_weight) return false;
    return Number(form.checked_weight) > Number(lookup.max_weight_kg);
  }

  function isAlreadyWeighed() {
    return Boolean(lookup?.checkin);
  }

  async function persistCheckin(overweightConfirmed = false) {
    const checkin = await fetchJson(`/competitions/${form.competition_id}/checkins`, {
      method: "POST",
      body: JSON.stringify({
        registration_id: lookup.registration_id,
        checked_weight: Number(form.checked_weight).toFixed(2),
        overweight_confirmed: overweightConfirmed,
      }),
    });
    setLookup({ ...lookup, checkin });
    setWarningOpen(false);
    setMessage([`${checkin.athlete.name} registrado na pesagem.`, checkin.is_overweight ? "error" : "success"]);
  }

  async function submit(event) {
    event.preventDefault();
    if (!lookup) {
      setMessage(["Localize o atleta pelo CPF antes de salvar a pesagem.", "error"]);
      return;
    }
    if (isAlreadyWeighed()) {
      setMessage(["Este atleta ja foi pesado nesta competicao. Nova pesagem bloqueada.", "error"]);
      return;
    }
    if (isOverweight()) {
      setWarningOpen(true);
      return;
    }
    try {
      await persistCheckin(false);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  async function confirmOverweight() {
    try {
      if (isAlreadyWeighed()) {
        setWarningOpen(false);
        setMessage(["Este atleta ja foi pesado nesta competicao. Nova pesagem bloqueada.", "error"]);
        return;
      }
      await persistCheckin(true);
    } catch (error) {
      setWarningOpen(false);
      setMessage([error.message, "error"]);
    }
  }

  return (
    <section className="workspace stack">
      <form className="registration registration-inline weighin-form" onSubmit={submit}>
        <div className="section-heading">
          <h2>Pesagem</h2>
          <span>{lookup?.checkin ? "Atleta ja pesado nesta competicao" : lookup ? categoryLabel(lookup.category) : "Localize o atleta pelo CPF"}</span>
        </div>
        <div className="grid weighin-row">
          <Select label="Competicao" value={form.competition_id} onChange={(competition_id) => {
            const next = { ...form, competition_id };
            setForm(next);
            findAthlete(next);
          }} required options={[["", "Selecione a competicao"], ...competitions.map((item) => [String(item.id), item.name])]} />
          <Field label="CPF" value={form.cpf} onBlur={() => findAthlete()} onChange={(cpf) => setForm({ ...form, cpf: maskCpf(cpf) })} required />
          <Field label="Peso checado" type="number" min="0" step="0.01" value={form.checked_weight} onChange={(checked_weight) => setForm({ ...form, checked_weight })} required disabled={!lookup || isAlreadyWeighed()} />
          <div className="inline-submit">
            <button className="primary" type="submit" disabled={!lookup || isAlreadyWeighed()}>Salvar pesagem</button>
          </div>
        </div>
        <div className="grid weighin-data">
          <Field label="Nome" value={lookup?.athlete.name || ""} readOnly placeholder="Atleta localizado" />
          <Field label="CPF" value={lookup?.athlete.cpf || ""} readOnly />
          <Field label="Faixa" value={lookup ? beltLabels[lookup.athlete.belt] || lookup.athlete.belt : ""} readOnly />
          <Field label="Categoria de idade" value={lookup?.category.age_group || ""} readOnly />
          <Field label="Categoria de peso" value={lookup?.category.weight_class || ""} readOnly />
          <Field label="Limite da categoria" value={lookup?.max_weight_kg ? `${lookup.max_weight_kg} kg` : "Sem limite superior"} readOnly />
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {warningOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <section className="weight-alert">
            <h2>Atleta nao bateu o peso</h2>
            <p>
              O peso informado foi {Number(form.checked_weight).toFixed(2)} kg e o limite da categoria e {lookup.max_weight_kg} kg.
            </p>
            <p>Confirma o registro mesmo assim?</p>
            <div className="actions">
              <button className="secondary" type="button" onClick={() => setWarningOpen(false)}>Cancelar</button>
              <button className="primary danger" type="button" onClick={confirmOverweight}>Confirmar pesagem</button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function CheckinPage() {
  const emptyForm = { competition_id: "", cpf: "" };
  const [competitions, setCompetitions] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [lookup, setLookup] = useState(null);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function findAthlete(nextForm = form) {
    setLookup(null);
    if (!nextForm.competition_id || normalizeCpf(nextForm.cpf).length !== 11) return;
    try {
      const data = await fetchJson(
        `/competitions/${nextForm.competition_id}/checkin-options?cpf=${encodeURIComponent(normalizeCpf(nextForm.cpf))}`,
      );
      setLookup(data);
      if (!data.checkin) {
        setMessage(["Atleta sem pesagem registrada. Status: No Show.", "error"]);
      } else if (data.checkin.is_overweight) {
        setMessage(["Atleta nao bateu o peso. Status: Out of weight.", "error"]);
      } else if (data.checkin.status === "Checked") {
        setMessage(["Atleta ja foi checado. Status: Checked.", "success"]);
      } else {
        setMessage(["Atleta localizado e apto para CHECKED.", "success"]);
      }
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const canReady = lookup?.checkin && !lookup.checkin.is_overweight && lookup.checkin.status !== "Checked";
  const canNotReady = Boolean(lookup?.checkin && lookup.checkin.status !== "Checked");

  async function setFightStatus(event, targetStatus) {
    event.preventDefault();
    if (!lookup) {
      setMessage(["Localize o atleta pelo CPF antes do checkin.", "error"]);
      return;
    }
    if (!lookup.checkin) {
      setMessage(["Atleta sem pesagem registrada. Status: No Show.", "error"]);
      return;
    }
    if (lookup.checkin.status === "Checked") {
      setMessage(["Atleta ja foi checado. Status: Checked.", "success"]);
      return;
    }
    if (targetStatus === "not-ready") {
      try {
        const checkin = await fetchJson(`/competitions/${form.competition_id}/checkins/${lookup.registration_id}/not-ready`, {
          method: "POST",
        });
        setLookup({ ...lookup, status: checkin.status, checkin });
        setMessage([`${checkin.athlete.name} marcado como ${checkin.status}.`, checkin.is_overweight ? "error" : "success"]);
      } catch (error) {
        setMessage([error.message, "error"]);
      }
      return;
    }
    if (lookup.checkin.is_overweight) {
      setMessage(["Atleta nao bateu o peso. Status: Out of weight.", "error"]);
      return;
    }
    try {
      const checkin = await fetchJson(`/competitions/${form.competition_id}/checkins/${lookup.registration_id}/ready`, {
        method: "POST",
      });
      setLookup({ ...lookup, status: checkin.status, checkin });
      setMessage([`${checkin.athlete.name} marcado como Checked.`, "success"]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  return (
    <section className="workspace stack">
      <form className="registration registration-inline weighin-form" onSubmit={(event) => setFightStatus(event, "ready")}>
        <div className="section-heading">
          <h2>Checkin</h2>
          <span>{lookup ? `Status: ${lookup.checkin?.status || lookup.status}` : "Localize o atleta pelo CPF"}</span>
        </div>
        <div className="grid ready-row">
          <Select label="Competicao" value={form.competition_id} onChange={(competition_id) => {
            const next = { ...form, competition_id };
            setForm(next);
            findAthlete(next);
          }} required options={[["", "Selecione a competicao"], ...competitions.map((item) => [String(item.id), item.name])]} />
          <Field label="CPF" value={form.cpf} onBlur={() => findAthlete()} onChange={(cpf) => setForm({ ...form, cpf: maskCpf(cpf) })} required />
          <div className="ready-actions">
            <button className="primary" type="submit" disabled={!canReady}>CHECKED</button>
            <button className="danger-button" type="button" disabled={!canNotReady} onClick={(event) => setFightStatus(event, "not-ready")}>NO CHECKED</button>
          </div>
        </div>
        <div className="grid weighin-data">
          <Field label="Nome" value={lookup?.athlete.name || ""} readOnly placeholder="Atleta localizado" />
          <Field label="CPF" value={lookup?.athlete.cpf || ""} readOnly />
          <Field label="Faixa" value={lookup ? beltLabels[lookup.athlete.belt] || lookup.athlete.belt : ""} readOnly />
          <Field label="Categoria de idade" value={lookup?.category.age_group || ""} readOnly />
          <Field label="Categoria de peso" value={lookup?.category.weight_class || ""} readOnly />
          <Field label="Status" value={lookup ? lookup.checkin?.status || lookup.status : ""} readOnly />
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
    </section>
  );
}

function FinalCheckPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function load(id) {
    setCompetitionId(id);
    setRows([]);
    if (!id) return;
    try {
      setRows(await fetchJson(`/competitions/${id}/final-checks`));
      setMessage(["", ""]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const groups = new Map();
  rows.forEach((item) => {
    const key = [item.category.belt, item.category.age_group, item.category.weight_class].join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });

  return (
    <section className="workspace stack">
      <section className="registration checkin-toolbar">
        <div className="section-heading">
          <h2>Checagem Final</h2>
          <span>{rows.length} atleta(s) na checagem final</span>
        </div>
        <div className="grid final-check-row">
          <Select label="Competicao" className="wide" value={competitionId} onChange={load} options={[["", "Selecione a competicao"], ...competitions.map((item) => [String(item.id), item.name])]} />
        </div>
        <Message text={message[0]} type={message[1]} />
      </section>
      <section className="panel checkin-panel">
        <div className="checkin-groups">
          {!competitionId && <div className="empty">Selecione uma competicao para consultar a checagem final.</div>}
          {competitionId && !rows.length && <div className="empty">Nenhum atleta inscrito nesta competicao.</div>}
          {[...groups.entries()].map(([key, items]) => <FinalCheckGroup groupKey={key} items={items} key={key} />)}
        </div>
      </section>
    </section>
  );
}

function FinalCheckGroup({ groupKey, items }) {
  const [belt, ageGroup, weight] = groupKey.split("|");
  return (
    <section className="checkin-group">
      <div className="checkin-group-heading">
        <h2>{[beltLabels[belt] || belt, ageGroup, weight].join(" | ")}</h2>
        <span>{items.length} atleta(s)</span>
      </div>
      <div className="checkin-table-wrap">
        <table className="checkin-table final-check-table">
          <thead><tr><th>Atleta</th><th>Peso checado</th><th>Status da checagem</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.registration_id}>
                <td data-label="Atleta">{item.athlete.name}</td>
                <td data-label="Peso checado">{item.checked_weight ? `${Number(item.checked_weight).toFixed(2)} kg` : "-"}</td>
                <td data-label="Status da checagem">
                  <span className={`check-status ${item.status.toLowerCase().replace(/\s+/g, "-")}`}>{item.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AthleteListPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [registrations, setRegistrations] = useState([]);
  const [filters, setFilters] = useState({ sex: "", belt: "", age_group: "", weight_class: "" });
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function load(id) {
    setCompetitionId(id);
    setRegistrations([]);
    if (!id) return;
    try {
      setRegistrations(await fetchJson(`/competitions/${id}/registrations`));
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  const values = (selector) => [...new Set(registrations.map(selector).filter(Boolean))].sort();
  const filtered = registrations.filter((item) => (
    (!filters.sex || item.athlete.sex === filters.sex) &&
    (!filters.belt || item.category.belt === filters.belt) &&
    (!filters.age_group || item.category.age_group === filters.age_group) &&
    (!filters.weight_class || item.category.weight_class === filters.weight_class)
  ));
  const groups = new Map();
  filtered.forEach((item) => {
    const key = [item.athlete.sex, item.category.belt, item.category.age_group, item.category.weight_class].join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });

  return (
    <section className="workspace stack">
      <section className="registration checkin-toolbar">
        <div className="section-heading"><h2>Listagem de Atletas</h2><span>{filtered.length} atleta(s) exibido(s) de {registrations.length} inscrito(s)</span></div>
        <div className="grid checkin-filters">
          <Select label="Competicao" className="wide" value={competitionId} onChange={load} options={[["", "Selecione a competicao"], ...competitions.map((item) => [String(item.id), item.name])]} />
          <Select label="Sexo" value={filters.sex} onChange={(sex) => setFilters({ ...filters, sex })} options={[["", "Todos"], ...values((item) => item.athlete.sex).map((value) => [value, sexLabels[value] || value])]} />
          <Select label="Faixa" value={filters.belt} onChange={(belt) => setFilters({ ...filters, belt })} options={[["", "Todas"], ...values((item) => item.category.belt).map((value) => [value, beltLabels[value] || value])]} />
          <Select label="Categoria" value={filters.age_group} onChange={(age_group) => setFilters({ ...filters, age_group })} options={[["", "Todas"], ...values((item) => item.category.age_group).map((value) => [value, value])]} />
          <Select label="Peso" value={filters.weight_class} onChange={(weight_class) => setFilters({ ...filters, weight_class })} options={[["", "Todos"], ...values((item) => item.category.weight_class).map((value) => [value, value])]} />
        </div>
        <Message text={message[0]} type={message[1]} />
      </section>
      <section className="panel checkin-panel">
        <div className="checkin-groups">
          {!registrations.length && <div className="empty">Nenhuma competicao selecionada ou nenhum atleta inscrito.</div>}
          {[...groups.entries()].map(([key, items]) => <CheckinGroup groupKey={key} items={items} key={key} />)}
        </div>
      </section>
    </section>
  );
}

function CheckinGroup({ groupKey, items }) {
  const [sex, belt, ageGroup, weight] = groupKey.split("|");
  return (
    <section className="checkin-group">
      <div className="checkin-group-heading">
        <h2>{[sexLabels[sex] || sex, beltLabels[belt] || belt, ageGroup, weight].join(" | ")}</h2>
        <span>{items.length} atleta(s)</span>
      </div>
      <div className="checkin-table-wrap">
        <table className="checkin-table">
          <thead><tr><th>Atleta</th><th>Equipe</th><th>CPF</th><th>Nascimento</th><th>Inscricao</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td data-label="Atleta">{item.athlete.name}</td>
                <td data-label="Equipe">{item.athlete.team?.name}</td>
                <td data-label="CPF">{item.athlete.cpf}</td>
                <td data-label="Nascimento">{item.athlete.birth_date}</td>
                <td data-label="Inscricao">#{item.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const ORDEM_REFRESH_MS = 2 * 60 * 1000;

// -- IBJJF category rules --
const IBJJF_AGE_GROUPS = [
  "Infantil 1", "Infantil 2", "Infantil 3", "Infantil 4", "Infantil 5",
  "Juvenil 1", "Juvenil 2",
  "Adulto", "Master 1", "Master 2", "Master 3", "Master 4", "Master 5", "Master 6", "Master 7",
];

const IBJJF_BELTS = {
  "Infantil 1":  ["white", "gray", "gray_white", "gray_black"],
  "Infantil 2":  ["white", "gray", "gray_white", "gray_black"],
  "Infantil 3":  ["white", "yellow", "yellow_white", "yellow_black"],
  "Infantil 4":  ["white", "yellow", "yellow_white", "yellow_black", "orange", "orange_white", "orange_black"],
  "Infantil 5":  ["white", "orange", "orange_white", "orange_black", "green", "green_white", "green_black"],
  "Juvenil 1":   ["white", "blue"],
  "Juvenil 2":   ["white", "blue", "purple"],
  "Adulto":      ["white", "blue", "purple", "brown", "black"],
  "Master 1":    ["white", "blue", "purple", "brown", "black"],
  "Master 2":    ["blue", "purple", "brown", "black"],
  "Master 3":    ["blue", "purple", "brown", "black"],
  "Master 4":    ["blue", "purple", "brown", "black"],
  "Master 5":    ["blue", "purple", "brown", "black"],
  "Master 6":    ["blue", "purple", "brown", "black"],
  "Master 7":    ["purple", "brown", "black"],
};

const IBJJF_WEIGHTS_KIDS = {
  "Infantil 1": ["-18kg", "-20kg", "-22kg", "-24kg", "-26kg", "-28kg", "+28kg"],
  "Infantil 2": ["-22kg", "-24kg", "-26kg", "-28kg", "-30kg", "-32kg", "+32kg"],
  "Infantil 3": ["-25kg", "-28kg", "-31kg", "-34kg", "-37kg", "-40kg", "+40kg"],
  "Infantil 4": ["-30kg", "-34kg", "-38kg", "-42kg", "-46kg", "-50kg", "+50kg"],
  "Infantil 5": ["-36kg", "-40kg", "-44kg", "-48kg", "-52kg", "-56kg", "+56kg"],
};

const IBJJF_WEIGHTS_STANDARD = [
  "Galo", "Pluma", "Pena", "Leve", "Medio", "Meio-Pesado", "Pesado", "Super-Pesado", "Pesadissimo",
];

function ibjjfWeights(ageGroup) {
  return IBJJF_WEIGHTS_KIDS[ageGroup] || IBJJF_WEIGHTS_STANDARD;
}

function buildAllIbjjfCategories() {
  const cats = [];
  for (const age_group of IBJJF_AGE_GROUPS) {
    for (const belt of IBJJF_BELTS[age_group]) {
      for (const weight_class of ibjjfWeights(age_group)) {
        cats.push({ age_group, belt, weight_class });
      }
    }
  }
  return cats;
}

function ConfigCategoriasPage() {
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({ age_group: "", belt: "", weight_class: "" });
  const [loading, setLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [message, setMessage] = useState(["", ""]);
  const [deleteId, setDeleteId] = useState(null);

  async function load() {
    try {
      const data = await fetchJson("/categories");
      setCategories(data);
    } catch (err) {
      setMessage([err.message, "error"]);
    }
  }

  useEffect(() => { load(); }, []);

  const validBelts = form.age_group ? (IBJJF_BELTS[form.age_group] || []) : [];
  const validWeights = form.age_group ? ibjjfWeights(form.age_group) : [];

  async function addCategory(e) {
    e.preventDefault();
    setLoading(true);
    setMessage(["", ""]);
    try {
      await fetchJson("/categories", { method: "POST", body: JSON.stringify(form) });
      setMessage(["Categoria criada com sucesso.", "success"]);
      setForm({ age_group: form.age_group, belt: "", weight_class: "" });
      await load();
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  async function importAll() {
    setImportLoading(true);
    setMessage(["", ""]);
    try {
      const all = buildAllIbjjfCategories();
      const existing = new Set(categories.map((c) => `${c.age_group}|${c.belt}|${c.weight_class}`));
      const toCreate = all.filter((c) => !existing.has(`${c.age_group}|${c.belt}|${c.weight_class}`));
      if (!toCreate.length) {
        setMessage(["Todas as categorias IBJJF ja estao cadastradas.", "success"]);
        return;
      }
      const created = await fetchJson("/categories/bulk", { method: "POST", body: JSON.stringify(toCreate) });
      setMessage([`${created.length} categoria(s) importada(s) com sucesso.`, "success"]);
      await load();
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setImportLoading(false);
    }
  }

  async function deleteCategory(id) {
    try {
      await fetchJson(`/categories/${id}`, { method: "DELETE" });
      setDeleteId(null);
      await load();
    } catch (err) {
      setMessage([err.message, "error"]);
    }
  }

  // group existing categories for display
  const grouped = useMemo(() => {
    const map = new Map();
    for (const cat of categories) {
      const key = cat.age_group;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(cat);
    }
    return [...map.entries()].sort(([a], [b]) => IBJJF_AGE_GROUPS.indexOf(a) - IBJJF_AGE_GROUPS.indexOf(b));
  }, [categories]);

  const allTotal = buildAllIbjjfCategories().length;
  const coverage = Math.round((categories.length / allTotal) * 100);

  return (
    <section className="workspace stack">
      <section className="registration panel">
        <div className="section-heading">
          <h2>Configuracao de Categorias IBJJF</h2>
          <span>{categories.length} cadastrada(s) de {allTotal} ({coverage}%)</span>
        </div>

        <div className="ccats-import-bar">
          <div>
            <p className="ccats-import-desc">
              Importa automaticamente todas as combinacoes validas de grupo de idade, faixa e peso conforme as regras da IBJJF.
            </p>
          </div>
          <button className="primary" onClick={importAll} disabled={importLoading} type="button">
            {importLoading ? "Importando..." : `Importar todas as categorias IBJJF (${allTotal})`}
          </button>
        </div>

        <div className="ccats-divider">ou adicione manualmente</div>

        <form onSubmit={addCategory}>
          <div className="grid ccats-form-row">
            <Select label="Grupo de Idade" value={form.age_group} onChange={(v) => setForm({ age_group: v, belt: "", weight_class: "" })} required options={[
              ["", "Selecione"],
              ...IBJJF_AGE_GROUPS.map((ag) => [ag, ag]),
            ]} />
            <Select label="Faixa" value={form.belt} onChange={(v) => setForm({ ...form, belt: v, weight_class: "" })} required disabled={!form.age_group} options={[
              ["", form.age_group ? "Selecione" : "Selecione a idade primeiro"],
              ...validBelts.map((b) => [b, beltLabels[b] || b]),
            ]} />
            <Select label="Categoria de Peso" value={form.weight_class} onChange={(v) => setForm({ ...form, weight_class: v })} required disabled={!form.belt} options={[
              ["", form.belt ? "Selecione" : "Selecione a faixa primeiro"],
              ...validWeights.map((w) => [w, w]),
            ]} />
            <div className="inline-submit">
              <button className="primary" type="submit" disabled={loading || !form.weight_class}>
                {loading ? "Salvando..." : "Adicionar"}
              </button>
            </div>
          </div>
          <Message text={message[0]} type={message[1]} />
        </form>
      </section>

      {grouped.length > 0 && (
        <section className="panel">
          <div className="section-heading"><h2>Categorias Cadastradas</h2></div>
          <div className="ccats-groups">
            {grouped.map(([ageGroup, cats]) => (
              <div key={ageGroup} className="ccats-group">
                <div className="ccats-group-header">{ageGroup}</div>
                <div className="ccats-group-body">
                  {cats
                    .sort((a, b) => (IBJJF_BELTS[ageGroup] || []).indexOf(a.belt) - (IBJJF_BELTS[ageGroup] || []).indexOf(b.belt) || ibjjfWeights(ageGroup).indexOf(a.weight_class) - ibjjfWeights(ageGroup).indexOf(b.weight_class))
                    .map((cat) => (
                      <div key={cat.id} className="ccats-item">
                        <span className="ccats-belt-dot" style={{ background: BELT_COLORS[cat.belt] || "#555" }} />
                        <span className="ccats-item-label">{beltLabels[cat.belt] || cat.belt} | {cat.weight_class}</span>
                        {deleteId === cat.id ? (
                          <div className="ccats-confirm">
                            <button className="danger-button compact-button" onClick={() => deleteCategory(cat.id)}>Confirmar</button>
                            <button className="secondary compact-button" onClick={() => setDeleteId(null)}>Cancelar</button>
                          </div>
                        ) : (
                          <button className="icon-button compact-button" title="Excluir" onClick={() => setDeleteId(cat.id)}>x</button>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {deleteId && (
        <div style={{display:"none"}} />
      )}
    </section>
  );
}

function OrdemPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [brackets, setBrackets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(["", ""]);
  const [dayFilter, setDayFilter] = useState(1);
  const [lastRefresh, setLastRefresh] = useState(null);
  const competitionIdRef = useRef("");

  useEffect(() => {
    fetchJson("/competitions")
      .then(setCompetitions)
      .catch((err) => setMessage([err.message, "error"]));
  }, []);

  async function fetchBrackets(id, silent = false) {
    if (!id) return;
    if (!silent) setLoading(true);
    try {
      const data = await fetchJson(`/competitions/${id}/brackets`);
      setBrackets(data);
      setLastRefresh(new Date());
      if (!data.length) setMessage(["Nenhuma chave gerada para esta competicao.", ""]);
      else if (!silent) setMessage(["", ""]);
    } catch (err) {
      if (!silent) setMessage([err.message, "error"]);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadBrackets(id) {
    setCompetitionId(id);
    competitionIdRef.current = id;
    setBrackets([]);
    setDayFilter(1);
    setMessage(["", ""]);
    setLastRefresh(null);
    await fetchBrackets(id, false);
  }

  useEffect(() => {
    const interval = setInterval(() => {
      if (competitionIdRef.current) fetchBrackets(competitionIdRef.current, true);
    }, ORDEM_REFRESH_MS);
    return () => clearInterval(interval);
  }, []);

  const allMatches = useMemo(() => {
    const result = [];
    for (const bracket of brackets) {
      const maxRound = Math.max(...bracket.matches.map((m) => m.round_number), 0);
      for (const match of bracket.matches) {
        if (!match.schedule) continue;
        if (match.result?.finalized) continue;
        result.push({ match, bracket, maxRound });
      }
    }
    return result;
  }, [brackets]);

  const days = useMemo(() => [...new Set(allMatches.map((m) => m.match.schedule.day_number))].sort(), [allMatches]);

  const matchesForDay = useMemo(
    () => allMatches.filter((m) => m.match.schedule.day_number === dayFilter),
    [allMatches, dayFilter]
  );

  const matColumns = useMemo(() => {
    const cols = new Map();
    for (const item of matchesForDay) {
      const mat = item.match.schedule.mat_number;
      if (!cols.has(mat)) cols.set(mat, []);
      cols.get(mat).push(item);
    }
    for (const [, items] of cols) {
      items.sort((a, b) => new Date(a.match.schedule.scheduled_start) - new Date(b.match.schedule.scheduled_start));
    }
    return [...cols.entries()].sort(([a], [b]) => a - b);
  }, [matchesForDay]);

  const competition = competitions.find((c) => String(c.id) === competitionId);

  return (
    <div className="ordem-page">
      <div className="ordem-top">
        <div className="ordem-comp-select">
          <label className="field">
            <span>Competicao</span>
            <select value={competitionId} onChange={(e) => loadBrackets(e.target.value)}>
              <option value="">Selecione a competicao</option>
              {competitions.map((c) => <option value={String(c.id)} key={c.id}>{c.name}</option>)}
            </select>
          </label>
        </div>
        {competition && (
          <div className="ordem-comp-info">
            <strong>{competition.name}</strong>
            <span>{new Date(competition.event_date).toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}</span>
          </div>
        )}
        {lastRefresh && (
          <div className="ordem-refresh-badge">
            <span>Atualizado as {lastRefresh.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
            <span className="ordem-refresh-hint">| proxima atualizacao em 2 min</span>
          </div>
        )}
      </div>

      {message[0] && <p className={`message ${message[1]}`}>{message[0]}</p>}
      {loading && <p className="message">Carregando lutas...</p>}

      {days.length > 1 && (
        <div className="cat-filter-bar">
          {days.map((d) => (
            <button
              key={d}
              className={`cat-filter-btn ${dayFilter === d ? "active" : ""}`}
              onClick={() => setDayFilter(d)}
            >Dia {d}</button>
          ))}
        </div>
      )}

      {matColumns.length > 0 && (
        <div className="ordem-mat-grid">
          {matColumns.map(([matNumber, items]) => (
            <div key={matNumber} className="ordem-mat-col">
              <div className="ordem-mat-header">
                <span className="ordem-mat-label">MAT {matNumber}</span>
                <span className="ordem-mat-count">{items.length} luta{items.length !== 1 ? "s" : ""}</span>
              </div>
              <div className="ordem-mat-fights">
                {items.map(({ match, bracket, maxRound }) => {
                  const sched = match.schedule;
                  const time = new Date(sched.scheduled_start).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
                  const round = roundLabel(match.round_number, maxRound);
                  const cat = bracket.category;
                  const finished = match.result?.finalized;
                  const athleteA = match.athlete_a;
                  const athleteB = match.athlete_b;
                  const winnerId = match.winner?.id;
                  return (
                    <div key={match.id} className={`ordem-fight ${finished ? "ordem-fight--done" : ""}`}>
                      <div className="ordem-fight-header">
                        <span className="ordem-fight-time">{time}</span>
                        <span className="ordem-fight-round">{round}</span>
                        {finished && <span className="ordem-fight-done">OK</span>}
                      </div>
                      <div className="ordem-fight-cat">
                        {cat.age_group} | {beltLabels[cat.belt] || cat.belt} | {cat.weight_class}
                      </div>
                      <div className="ordem-fight-athletes">
                        <OrdemAthlete athlete={athleteA} winnerId={winnerId} side="a" />
                        <div className="ordem-fight-vs">* * *</div>
                        <OrdemAthlete athlete={athleteB} winnerId={winnerId} side="b" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && competitionId && !matColumns.length && !message[0] && (
        <div className="empty">Nenhuma luta agendada. Gere as chaves e o cronograma primeiro.</div>
      )}
    </div>
  );
}

function OrdemAthlete({ athlete, winnerId, side }) {
  const isWinner = athlete && winnerId === athlete.id;
  const isLoser = winnerId && athlete && winnerId !== athlete.id;
  return (
    <div className={`ordem-athlete ${isWinner ? "ordem-athlete--winner" : ""} ${isLoser ? "ordem-athlete--loser" : ""}`}>
      {athlete ? (
        <>
          <span className="ordem-athlete-name">{athlete.name}</span>
          <span className="ordem-athlete-team">{athlete.team?.name || "-"}</span>
        </>
      ) : (
        <span className="ordem-athlete-tbd">A definir</span>
      )}
    </div>
  );
}

const SEX_LABELS = { male: "Masculino", female: "Feminino" };
const BELT_ORDER = ["white","gray","gray_white","gray_black","yellow","yellow_white","yellow_black","orange","orange_white","orange_black","green","green_white","green_black","blue","purple","brown","black","red_black","red_white","red"];
const BELT_COLORS = {
  white: "#f0f0f0", gray: "#9e9e9e", gray_white: "#bdbdbd", gray_black: "#757575",
  yellow: "#f9c107", yellow_white: "#fdd835", yellow_black: "#f9a825",
  orange: "#f57c00", orange_white: "#fb8c00", orange_black: "#e65100",
  green: "#388e3c", green_white: "#66bb6a", green_black: "#1b5e20",
  blue: "#1565c0", purple: "#6a1b9a", brown: "#4e342e",
  black: "#212121", red_black: "#b71c1c", red_white: "#e53935", red: "#c62828",
};

function CategoriasPage() {
  const [competitions, setCompetitions] = useState([]);
  const [competitionId, setCompetitionId] = useState("");
  const [brackets, setBrackets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(["", ""]);
  const [sexFilter, setSexFilter] = useState("");
  const [ageFilter, setAgeFilter] = useState("");
  const [beltFilter, setBeltFilter] = useState("");

  useEffect(() => {
    fetchJson("/competitions")
      .then(setCompetitions)
      .catch((err) => setMessage([err.message, "error"]));
  }, []);

  async function loadBrackets(id) {
    setCompetitionId(id);
    setBrackets([]);
    setSexFilter("");
    setAgeFilter("");
    setBeltFilter("");
    setMessage(["", ""]);
    if (!id) return;
    setLoading(true);
    try {
      const data = await fetchJson(`/competitions/${id}/brackets`);
      setBrackets(data);
      if (!data.length) setMessage(["Nenhuma chave gerada para esta competicao.", ""]);
    } catch (err) {
      setMessage([err.message, "error"]);
    } finally {
      setLoading(false);
    }
  }

  const availableSexes = [...new Set(
    brackets.flatMap((b) => b.entries.filter((e) => e.athlete).map((e) => e.athlete.sex))
  )].sort();

  const filtered = brackets.filter((b) => {
    const athletes = b.entries.filter((e) => e.athlete);
    if (sexFilter && !athletes.some((e) => e.athlete.sex === sexFilter)) return false;
    if (ageFilter && b.category.age_group !== ageFilter) return false;
    if (beltFilter && b.category.belt !== beltFilter) return false;
    return true;
  });

  const ageGroups = [...new Set(
    brackets
      .filter((b) => {
        if (!sexFilter) return true;
        return b.entries.filter((e) => e.athlete).some((e) => e.athlete.sex === sexFilter);
      })
      .map((b) => b.category.age_group)
  )].sort();

  const belts = [...new Set(
    brackets
      .filter((b) => {
        if (!sexFilter) return true;
        return b.entries.filter((e) => e.athlete).some((e) => e.athlete.sex === sexFilter);
      })
      .filter((b) => !ageFilter || b.category.age_group === ageFilter)
      .map((b) => b.category.belt)
  )].sort((a, z) => BELT_ORDER.indexOf(a) - BELT_ORDER.indexOf(z));

  const competition = competitions.find((c) => String(c.id) === competitionId);

  return (
    <div className="categorias-page">
      <div className="categorias-top">
        <div className="categorias-comp-select">
          <label className="field">
            <span>Competicao</span>
            <select value={competitionId} onChange={(e) => loadBrackets(e.target.value)}>
              <option value="">Selecione a competicao</option>
              {competitions.map((c) => <option value={String(c.id)} key={c.id}>{c.name}</option>)}
            </select>
          </label>
        </div>
        {competition && (
          <div className="categorias-comp-info">
            <strong>{competition.name}</strong>
            <span>{new Date(competition.event_date).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" })}</span>
          </div>
        )}
      </div>

      {message[0] && <p className={`message ${message[1]}`}>{message[0]}</p>}
      {loading && <p className="message">Carregando chaves...</p>}

      {!!brackets.length && (
        <>
          {availableSexes.length > 1 && (
            <div className="cat-filter-bar">
              <button
                className={`cat-filter-btn ${!sexFilter ? "active" : ""}`}
                onClick={() => { setSexFilter(""); setAgeFilter(""); setBeltFilter(""); }}
              >Todos</button>
              {availableSexes.map((s) => (
                <button
                  key={s}
                  className={`cat-filter-btn ${sexFilter === s ? "active" : ""}`}
                  onClick={() => { setSexFilter(s); setAgeFilter(""); setBeltFilter(""); }}
                >{SEX_LABELS[s] || s}</button>
              ))}
            </div>
          )}

          {ageGroups.length > 1 && (
            <div className="cat-filter-bar cat-filter-bar--secondary">
              <button
                className={`cat-filter-btn cat-filter-btn--sm ${!ageFilter ? "active" : ""}`}
                onClick={() => { setAgeFilter(""); setBeltFilter(""); }}
              >Todas as idades</button>
              {ageGroups.map((ag) => (
                <button
                  key={ag}
                  className={`cat-filter-btn cat-filter-btn--sm ${ageFilter === ag ? "active" : ""}`}
                  onClick={() => { setAgeFilter(ag); setBeltFilter(""); }}
                >{ag}</button>
              ))}
            </div>
          )}

          {belts.length > 1 && (
            <div className="cat-filter-bar cat-filter-bar--belts">
              <button
                className={`cat-filter-btn cat-filter-btn--sm ${!beltFilter ? "active" : ""}`}
                onClick={() => setBeltFilter("")}
              >Todas as faixas</button>
              {belts.map((belt) => (
                <button
                  key={belt}
                  className={`cat-filter-btn cat-filter-btn--sm cat-filter-btn--belt ${beltFilter === belt ? "active" : ""}`}
                  style={{ "--belt-color": BELT_COLORS[belt] || "#555" }}
                  onClick={() => setBeltFilter(belt)}
                >{beltLabels[belt] || belt}</button>
              ))}
            </div>
          )}

          <div className="categorias-summary">
            <span>{filtered.length} categoria(s) exibida(s)</span>
          </div>

          {filtered.length === 0 ? (
            <div className="empty">Nenhuma categoria encontrada para os filtros selecionados.</div>
          ) : (
            <div className="cat-grid">
              {filtered.map((b) => {
                const athletes = b.entries.filter((e) => e.athlete);
                const matches = b.matches.filter((m) => m.status !== "bye");
                const done = b.matches.filter((m) => m.status === "finished").length;
                const belt = b.category.belt;
                return (
                  <a key={b.id} className="cat-card" href={`/chaves/${b.id}`}>
                    <div className="cat-card-belt" style={{ background: BELT_COLORS[belt] || "#555" }} />
                    <div className="cat-card-body">
                      <div className="cat-card-age">{b.category.age_group}</div>
                      <div className="cat-card-belt-label">{beltLabels[belt] || belt}</div>
                      <div className="cat-card-weight">{b.category.weight_class}</div>
                      <div className="cat-card-stats">
                        <span>{athletes.length} atleta{athletes.length !== 1 ? "s" : ""}</span>
                        {matches.length > 0 && (
                          <span className={done === matches.length ? "cat-stat-done" : ""}>{done}/{matches.length} luta{matches.length !== 1 ? "s" : ""}</span>
                        )}
                      </div>
                    </div>
                    <div className="cat-card-arrow">&rsaquo;</div>
                  </a>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, value, onChange, className = "", ...props }) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange?.(event.target.value)} {...props} />
    </label>
  );
}

function Select({ label, value, onChange, options, className = "", ...props }) {
  return (
    <label className={`field ${className}`.trim()}>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} {...props}>
        {options.map(([optionValue, labelText]) => <option value={optionValue} key={`${optionValue}-${labelText}`}>{labelText}</option>)}
      </select>
    </label>
  );
}

ReactDOM.createRoot(document.querySelector("#root")).render(<App />);
