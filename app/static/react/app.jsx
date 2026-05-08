const { useEffect, useLayoutEffect, useMemo, useRef, useState } = React;

const routes = [
  ["/cadastros", "ATHLETES"],
  ["/equipes", "ACADEMIES"],
  ["/competicoes", "CHAMPIONSHIPS"],
  ["/inscricoes", "REGISTRATION"],
  ["/chaves", "BRACKETS"],
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

function Message({ text, type }) {
  return <p className={`message ${type || ""}`.trim()} role="status" aria-live="polite">{text}</p>;
}

function App() {
  const path = window.location.pathname === "/" ? "/cadastros" : window.location.pathname;
  const [apiOk, setApiOk] = useState(false);

  useEffect(() => {
    fetchJson("/health").then(() => setApiOk(true)).catch(() => setApiOk(false));
  }, []);

  const title = routes.find(([route]) => route === path)?.[1] || "ATHLETES";
  const isBracket = path === "/chaves";

  return (
    <>
      <header className="ibjjf-mainbar">
        <a className="brand" href="/cadastros" aria-label="FJJPE">
          <img className="brand-logo" src="/static/fjjpe-logo.png" alt="FJJPE" />
          <strong>FJJPE</strong>
        </a>
        <nav className="site-nav" aria-label="Principal">
          {routes.map(([route, label]) => (
            <a className={route === path ? "active" : ""} href={route} key={route}>
              {label}
            </a>
          ))}
        </nav>
        <div className={`status top-status ${apiOk ? "ok" : ""}`}>{apiOk ? "Online" : "Conectando"}</div>
      </header>
      <section className="page-title-band">
        <h1>{title}</h1>
      </section>
      <main className={`shell ${isBracket ? "bracket-shell" : ""}`.trim()}>
        {path === "/equipes" && <TeamsPage />}
        {path === "/competicoes" && <CompetitionsPage />}
        {path === "/inscricoes" && <RegistrationsPage />}
        {path === "/chaves" && <BracketsPage />}
        {path === "/checagem" && <AthleteListPage />}
        {path === "/checkin/pesagem" && <WeighinPage />}
        {path === "/checkin" && <CheckinPage />}
        {path === "/checagem-final" && <FinalCheckPage />}
        {path === "/ranking" && <RankingPage />}
        {!["/equipes", "/competicoes", "/inscricoes", "/chaves", "/checagem", "/checkin/pesagem", "/checkin", "/checagem-final", "/ranking"].includes(path) && (
          <AthletesPage />
        )}
      </main>
    </>
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
    fetchJson("/teams?limit=100&offset=0")
      .then((page) => setTeams(page.items))
      .catch((error) => setMessage([error.message, "error"]));
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
    setLoading(true);
    try {
      const athlete = await fetchJson("/athletes", {
        method: "POST",
        body: JSON.stringify({ ...form, team_id: Number(form.team_id) }),
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
          <span>{teams.length ? `Equipes: ${teams.length}` : "Carregando equipes"}</span>
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
          <Select label="Equipe" value={form.team_id} onChange={(team_id) => setForm({ ...form, team_id })} required disabled={!teams.length} options={[
            ["", teams.length ? "Selecione a equipe" : "Nenhuma equipe cadastrada"],
            ...teams.sort((a, b) => a.name.localeCompare(b.name)).map((team) => [String(team.id), team.name]),
          ]} />
          <Select label="Faixa" value={form.belt} onChange={(belt) => setForm({ ...form, belt })} required options={[
            ["", "Selecione"],
            ...beltOptions,
          ]} />
          <Field label="Data da graduacao" type="date" value={form.graduation_date} onChange={(graduation_date) => setForm({ ...form, graduation_date })} required />
          <Field label="Data de nascimento" type="date" value={form.birth_date} onChange={(birth_date) => setForm({ ...form, birth_date })} required />
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={loading || !teams.length}>Cadastrar atleta</button>
        </div>
        <Message text={cpfError || message[0]} type={cpfError ? "error" : message[1]} />
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
  const [form, setForm] = useState({ name: "", event_date: "", mat_count: "4" });
  const [count, setCount] = useState(0);
  const [message, setMessage] = useState(["", ""]);

  async function loadCount() {
    const competitions = await fetchJson("/competitions");
    setCount(competitions.length);
  }

  useEffect(() => {
    loadCount().catch((error) => setMessage([error.message, "error"]));
  }, []);

  async function submit(event) {
    event.preventDefault();
    try {
      const competition = await fetchJson("/competitions", {
        method: "POST",
        body: JSON.stringify({ ...form, mat_count: Number(form.mat_count) }),
      });
      setMessage([`Competicao ${competition.name} cadastrada.`, "success"]);
      setForm({ name: "", event_date: "", mat_count: "4" });
      await loadCount();
    } catch (error) {
      setMessage([error.message, "error"]);
    }
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
    </section>
  );
}

function RegistrationsPage() {
  const [competitions, setCompetitions] = useState([]);
  const [form, setForm] = useState({ competition_id: "", cpf: "", birth_date: "", category_id: "" });
  const [options, setOptions] = useState(null);
  const [status, setStatus] = useState("Informe competicao, CPF e nascimento");
  const [message, setMessage] = useState(["", ""]);

  useEffect(() => {
    fetchJson("/competitions").then(setCompetitions).catch((error) => setMessage([error.message, "error"]));
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
      setStatus(`${data.age_group} | ${data.age} anos`);
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
      setForm({ competition_id: form.competition_id, cpf: "", birth_date: "", category_id: "" });
      setOptions(null);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

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
          <Field label="Atleta confirmado" value={options ? `${options.athlete.name} | ${options.athlete.team.name} | ${options.athlete.belt}` : ""} readOnly placeholder="Atleta confirmado apos validacao" />
          <Select label="Categoria" value={form.category_id} onChange={(category_id) => setForm({ ...form, category_id })} required disabled={!options} options={[
            ["", options ? "Selecione a categoria" : "Categoria calculada apos validacao"],
            ...(options?.categories || []).map((category) => [String(category.id), categoryLabel(category)]),
          ]} />
          <div className="inline-submit">
            <button className="primary" type="submit" disabled={!options}>Inscrever atleta</button>
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
  const [fightPanel, setFightPanel] = useState(null);
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
      const registrations = await fetchJson(`/competitions/${id}/registrations`);
      const categories = new Map();
      registrations.forEach((registration) => {
        const key = String(registration.category.id);
        const current = categories.get(key) || { category: registration.category, count: 0 };
        categories.set(key, { ...current, count: current.count + 1 });
      });
      setCategoryOptions([...categories.values()].sort((left, right) => {
        return categoryLabel(left.category).localeCompare(categoryLabel(right.category));
      }));
      setMessage(["", ""]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  async function generateCategory(event) {
    event.preventDefault();
    try {
      const bracket = await fetchJson(`/competitions/${competitionId}/brackets`, {
        method: "POST",
        body: JSON.stringify({ category_id: Number(categoryId), replace_existing: true }),
      });
      setResult({
        competition_id: Number(competitionId),
        generated_count: 1,
        skipped_count: 0,
        brackets: [bracket],
      });
      setMessage(["Chave da categoria gerada com sucesso.", "success"]);
    } catch (error) {
      setMessage([error.message, "error"]);
    }
  }

  async function generateAll() {
    try {
      const data = await fetchJson(`/competitions/${competitionId}/brackets/generate-all`, {
        method: "POST",
        body: JSON.stringify({ replace_existing: true }),
      });
      setResult(data);
      setMessage(["Todas as chaves foram geradas com sucesso.", "success"]);
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
          <div className="inline-submit">
            <button className="secondary" type="button" onClick={generateAll} disabled={!competitionId}>Gerar todas</button>
          </div>
        </div>
        <Message text={message[0]} type={message[1]} />
      </form>
      {result && (
        <section className="registration bracket-result">
          <div className="section-heading">
            <h2>Chaves Geradas</h2>
            <span>{result.generated_count} chave(s) gerada(s)</span>
          </div>
          <div className="landscape-scroll" aria-label="Chaves em formato paisagem">
            <div className="ibjjf-sheets">
              {result.brackets.map((bracket) => <BracketSheet bracket={bracket} key={bracket.id} onOpenFight={(match, matchNumber) => setFightPanel({ bracket, match, matchNumber })} />)}
            </div>
          </div>
        </section>
      )}
      {fightPanel && <FightPanel data={fightPanel} onClose={() => setFightPanel(null)} />}
    </section>
  );
}

function BracketSheet({ bracket, onOpenFight }) {
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
          <span>{summary}</span>
        </div>
        <div className={`ibjjf-board ${bracket.rounds >= 4 ? "split-brackets" : ""}`.trim()}>
          {bracket.rounds >= 4 ? <SplitBracket bracket={bracket} onOpenFight={onOpenFight} /> : <CompactBracket bracket={bracket} onOpenFight={onOpenFight} />}
        </div>
      </section>
      <div className="ibjjf-sheet-actions">
        <button className="secondary" type="button" onClick={exportPdf} disabled={exporting}>
          {exporting ? "Exportando PDF" : "Exportar PDF"}
        </button>
        {exportError && <span className="pdf-error">{exportError}</span>}
      </div>
    </section>
  );
}

function CompactBracket({ bracket, onOpenFight }) {
  const halfSize = bracket.bracket_size / 2;
  const sideA = bracket.matches.filter((match) => match.round_number < bracket.rounds && match.position_end <= halfSize);
  const sideB = bracket.matches.filter((match) => match.round_number < bracket.rounds && match.position_start > halfSize);
  const finalMatch = bracket.matches.find((match) => match.round_number === bracket.rounds);
  const matchNumbers = bracketMatchNumbers(sideA, sideB, finalMatch);
  return (
    <div className="ibjjf-compact-board">
      <BracketSide title="Lado A" subtitle={`Posicoes 1-${halfSize}`} matches={sideA} totalRounds={bracket.rounds} direction="left" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
      <FinalSection match={finalMatch} title="Final" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
      <BracketSide title="Lado B" subtitle={`Posicoes ${halfSize + 1}-${bracket.bracket_size}`} matches={sideB} totalRounds={bracket.rounds} direction="right" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
    </div>
  );
}

function SplitBracket({ bracket, onOpenFight }) {
  return (
    <>
      <BracketHalf bracket={bracket} index={1} start={1} end={bracket.bracket_size / 2} onOpenFight={onOpenFight} />
      <BracketHalf bracket={bracket} index={2} start={bracket.bracket_size / 2 + 1} end={bracket.bracket_size} onOpenFight={onOpenFight} />
      <section className="ibjjf-finals-block">
        <div className="ibjjf-bracket-block-title">FINALS</div>
        <div className="ibjjf-finals-center">
          <FinalSection match={bracket.matches.find((match) => match.round_number === bracket.rounds)} title="Final" onOpenFight={onOpenFight} />
        </div>
      </section>
    </>
  );
}

function BracketHalf({ bracket, index, start, end, onOpenFight }) {
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
          <BracketSide title={`Lado ${index}A`} subtitle={`Posicoes ${start}-${middle}`} matches={left} totalRounds={bracket.rounds} direction="left" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
          <FinalSection match={finalMatch} title="Final do bracket" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
          <BracketSide title={`Lado ${index}B`} subtitle={`Posicoes ${middle + 1}-${end}`} matches={right} totalRounds={bracket.rounds} direction="right" matchNumbers={matchNumbers} onOpenFight={onOpenFight} />
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

function BracketSide({ title, subtitle, matches, totalRounds, direction, matchNumbers, onOpenFight }) {
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
                <MatchCard match={match} direction={direction} key={match.id} matchNumber={matchNumbers?.get(match.id)} onOpenFight={onOpenFight} />
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

function FinalSection({ match, title, matchNumbers, onOpenFight }) {
  return (
    <section className="ibjjf-final-section">
      <div className="ibjjf-side-header final-header"><strong>{title}</strong><span>Vencedor do Lado A x Vencedor do Lado B</span></div>
      <div className="ibjjf-final-match">{match && <MatchCard match={match} direction="final" matchNumber={matchNumbers?.get(match.id)} onOpenFight={onOpenFight} />}</div>
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

function MatchCard({ match, direction, matchNumber, onOpenFight }) {
  const left = match.athlete_a || { name: "A definir", team: { name: "" } };
  const right = match.athlete_b || { name: "A definir", team: { name: "" } };
  const athleteName = (athlete) => `${athlete.name}${athlete.is_ranked ? " *" : ""}`;
  const checkinClass = (athlete) => (athlete.checkin_status || "No Show").toLowerCase().replace(/\s+/g, "-");
  const athleteLine = (athlete) => (
    <span className="ibjjf-athlete-line">
      {athlete.id && <span className={`bracket-check-status ${checkinClass(athlete)}`} title={athlete.checkin_status || "No Show"} />}
      <strong>{athleteName(athlete)}</strong>
    </span>
  );
  const displayedMatchNumber = matchNumber || match.match_number;
  const matchLabel = match.status === "bye"
    ? `Luta ${displayedMatchNumber} | BYE`
    : `Luta ${displayedMatchNumber}`;
  return (
    <article className={`ibjjf-match ${direction}`} role="button" tabIndex="0" onClick={() => onOpenFight?.(match, displayedMatchNumber)} onKeyDown={(event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onOpenFight?.(match, displayedMatchNumber);
      }
    }}>
      <div className="ibjjf-match-meta"><strong>{matchLabel}</strong><span>Mat 10</span></div>
      <div className="ibjjf-slot winner">
        <span className="ibjjf-position">{match.position_start}</span>
        <div>{athleteLine(left)}<small>{left.team?.name || ""}</small></div>
      </div>
      <div className="ibjjf-slot">
        <span className="ibjjf-position">{match.position_end}</span>
        <div>{athleteLine(right)}<small>{right.team?.name || ""}</small></div>
      </div>
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

function FightPanel({ data, onClose }) {
  const { bracket, match, matchNumber } = data;
  const duration = fightDurationSeconds(bracket.category);
  const [timeLeft, setTimeLeft] = useState(duration);
  const [running, setRunning] = useState(false);
  const [scores, setScores] = useState({
    a: { points: 0, advantages: 0, penalties: 0 },
    b: { points: 0, advantages: 0, penalties: 0 },
  });
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
    setScores((current) => ({
      ...current,
      [side]: {
        ...current[side],
        [field]: current[side][field] + 1,
      },
    }));
  }

  return (
    <div className="modal-backdrop fight-modal-backdrop" role="dialog" aria-modal="true">
      <section className="fight-panel">
        <button className="fight-close" type="button" onClick={onClose} aria-label="Fechar painel de luta">x</button>
        <div className="fight-rows">
          <FightAthleteRow athlete={athleteA} score={scores.a} active onScore={(field) => addScore("a", field)} />
          <FightAthleteRow athlete={athleteB} score={scores.b} onScore={(field) => addScore("b", field)} />
        </div>
        <footer className="fight-footer">
          <div className="fight-info">
            <strong>{categoryText}</strong>
            <span>Luta {matchNumber} {match.status === "bye" ? "| BYE" : ""}</span>
            <button className="secondary" type="button" onClick={() => {
              setRunning(false);
              setTimeLeft(duration);
            }}>Reset</button>
          </div>
          <button className={`fight-clock ${running ? "running" : ""}`} type="button" onClick={() => setRunning((current) => !current)}>
            {formatFightTime(timeLeft)}
          </button>
        </footer>
      </section>
    </div>
  );
}

function FightAthleteRow({ athlete, score, active = false, onScore }) {
  return (
    <section className={`fight-athlete-row ${active ? "active" : ""}`.trim()}>
      <div className="fight-athlete-info">
        <div className="fight-athlete-name"><span className="fight-flag" aria-label="Brasil">🇧🇷</span><strong>{athlete.name}</strong></div>
        <span>{athlete.team?.name || ""}</span>
      </div>
      <button className="fight-score points" type="button" onClick={() => onScore("points")} aria-label={`Adicionar ponto para ${athlete.name}`}>
        {score.points}
      </button>
      <button className="fight-score advantages" type="button" onClick={() => onScore("advantages")} aria-label={`Adicionar vantagem para ${athlete.name}`}>
        {score.advantages}
      </button>
      <button className="fight-score penalties" type="button" onClick={() => onScore("penalties")} aria-label={`Adicionar punicao para ${athlete.name}`}>
        {score.penalties}
      </button>
    </section>
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
