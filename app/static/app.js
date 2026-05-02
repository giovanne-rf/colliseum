const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  athleteForm: document.querySelector("#athleteForm"),
  name: document.querySelector("#name"),
  cpf: document.querySelector("#cpf"),
  email: document.querySelector("#email"),
  phone: document.querySelector("#phone"),
  team: document.querySelector("#team"),
  belt: document.querySelector("#belt"),
  graduationDate: document.querySelector("#graduationDate"),
  birthDate: document.querySelector("#birthDate"),
  formMessage: document.querySelector("#formMessage"),
  teamsStatus: document.querySelector("#teamsStatus"),
  submitButton: document.querySelector("#submitButton"),
  reloadAthletes: document.querySelector("#reloadAthletes"),
  athleteList: document.querySelector("#athleteList"),
  teamFilter: document.querySelector("#teamFilter"),
  beltFilter: document.querySelector("#beltFilter"),
};

const state = {
  teams: [],
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setMessage(text, type = "") {
  elements.formMessage.textContent = text;
  elements.formMessage.className = `message ${type}`.trim();
}

function beltLabel(belt) {
  return {
    white: "Branca",
    blue: "Azul",
    purple: "Roxa",
    brown: "Marrom",
    black: "Preta",
  }[belt] || belt;
}

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

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function populateTeams() {
  elements.team.innerHTML = "";

  if (!state.teams.length) {
    elements.team.add(new Option("Nenhuma equipe cadastrada", ""));
    elements.team.disabled = true;
    elements.teamsStatus.textContent = "Equipes: 0";
    elements.submitButton.disabled = true;
    setMessage("Cadastre ou importe equipes antes de cadastrar atletas.", "error");
    return;
  }

  elements.team.add(new Option("Selecione a equipe", ""));
  const sortedTeams = [...state.teams].sort((left, right) => left.name.localeCompare(right.name));
  for (const team of sortedTeams) {
    elements.team.add(new Option(team.name, String(team.id)));
  }

  elements.team.disabled = false;
  elements.teamsStatus.textContent = `Equipes: ${state.teams.length}`;
  elements.submitButton.disabled = false;
  setMessage("");
}

async function loadTeams() {
  elements.team.disabled = true;
  elements.teamsStatus.textContent = "Equipes: carregando...";
  elements.team.innerHTML = '<option value="">Carregando equipes...</option>';
  try {
    const page = await fetchJson("/teams?limit=100&offset=0");
    state.teams = page.items;
    populateTeams();
  } catch (error) {
    state.teams = [];
    elements.team.innerHTML = '<option value="">Erro ao carregar equipes</option>';
    elements.teamsStatus.textContent = "Equipes: erro";
    elements.submitButton.disabled = true;
    throw error;
  }
}

function renderAthletes(items) {
  elements.athleteList.innerHTML = "";

  if (!items.length) {
    elements.athleteList.innerHTML = '<div class="empty">Nenhum atleta encontrado</div>';
    return;
  }

  for (const athlete of items) {
    const card = document.createElement("article");
    card.className = "athlete-card";
    card.innerHTML = `
      <strong>${athlete.name}</strong>
      <dl>
        <dt>Equipe</dt><dd>${athlete.team.name}</dd>
        <dt>Faixa</dt><dd>${beltLabel(athlete.belt)}</dd>
        <dt>Graduacao</dt><dd>${athlete.graduation_date}</dd>
        <dt>CPF</dt><dd>${athlete.cpf}</dd>
        <dt>Email</dt><dd>${athlete.email}</dd>
        <dt>Telefone</dt><dd>${athlete.phone}</dd>
        <dt>Idade</dt><dd>${athlete.age}</dd>
      </dl>
    `;
    elements.athleteList.append(card);
  }
}

async function loadAthletes() {
  const params = new URLSearchParams({ limit: "25", offset: "0" });
  const team = elements.teamFilter.value.trim();
  const belt = elements.beltFilter.value;

  if (team) {
    const matchedTeam = state.teams.find((item) =>
      item.name.toLowerCase().includes(team.toLowerCase()),
    );
    if (matchedTeam) {
      params.set("team_id", String(matchedTeam.id));
    }
  }
  if (belt) params.set("belt", belt);

  const page = await fetchJson(`/athletes?${params.toString()}`);
  renderAthletes(page.items);
}

function buildAthletePayload() {
  const payload = {
    name: elements.name.value.trim(),
    cpf: elements.cpf.value.trim(),
    email: elements.email.value.trim(),
    phone: elements.phone.value.trim(),
    team_id: Number(elements.team.value),
    belt: elements.belt.value,
    graduation_date: elements.graduationDate.value,
    birth_date: elements.birthDate.value,
  };

  return payload;
}

async function submitAthlete(event) {
  event.preventDefault();
  setMessage("");

  if (!elements.athleteForm.reportValidity()) {
    return;
  }

  elements.submitButton.disabled = true;
  try {
    const athlete = await fetchJson("/athletes", {
      method: "POST",
      body: JSON.stringify(buildAthletePayload()),
    });
    setMessage(`Atleta ${athlete.name} cadastrado com sucesso.`, "success");
    elements.athleteForm.reset();
    populateTeams();
    await loadAthletes();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.submitButton.disabled = false;
  }
}

function maskCpf(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function normalizeCpf(value) {
  return value.replace(/\D/g, "");
}

function isValidCpf(value) {
  const digits = normalizeCpf(value);
  if (digits.length !== 11) {
    return false;
  }
  if (digits === digits[0].repeat(11)) {
    return false;
  }

  const numbers = [...digits].map(Number);
  const firstSum = numbers.slice(0, 9).reduce((total, number, index) => {
    return total + number * (10 - index);
  }, 0);
  let firstDigit = (firstSum * 10) % 11;
  if (firstDigit === 10) {
    firstDigit = 0;
  }

  const secondSum = numbers.slice(0, 10).reduce((total, number, index) => {
    return total + number * (11 - index);
  }, 0);
  let secondDigit = (secondSum * 10) % 11;
  if (secondDigit === 10) {
    secondDigit = 0;
  }

  return numbers[9] === firstDigit && numbers[10] === secondDigit;
}

function validateCpfField() {
  const value = elements.cpf.value.trim();
  const isEmpty = value.length === 0;
  const isValid = !isEmpty && isValidCpf(value);
  elements.cpf.setCustomValidity(isEmpty || isValid ? "" : "Informe um CPF valido.");
  return isEmpty || isValid;
}

function warnInvalidCpfOnBlur() {
  const value = elements.cpf.value.trim();
  if (!value) {
    setMessage("");
    return;
  }

  if (!validateCpfField()) {
    setMessage("CPF invalido. Verifique os digitos informados.", "error");
    elements.cpf.reportValidity();
    return;
  }

  setMessage("");
}

function maskPhone(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/(\d{2})(\d)/, "$1-$2")
    .replace(/(\d{5})(\d{1,4})$/, "$1.$2");
}

async function bootstrap() {
  try {
    await fetchJson("/health");
    setStatus("Online", true);
    await loadTeams();
    await loadAthletes();
  } catch (error) {
    setStatus("Offline", false);
    setMessage(error.message, "error");
  }
}

elements.athleteForm.addEventListener("submit", submitAthlete);
elements.reloadAthletes.addEventListener("click", loadAthletes);
elements.teamFilter.addEventListener("input", () => window.clearTimeout(elements.teamFilter.timer));
elements.teamFilter.addEventListener("input", () => {
  window.clearTimeout(elements.teamFilter.timer);
  elements.teamFilter.timer = window.setTimeout(loadAthletes, 300);
});
elements.beltFilter.addEventListener("change", loadAthletes);
elements.cpf.addEventListener("input", () => {
  elements.cpf.value = maskCpf(elements.cpf.value);
  validateCpfField();
});
elements.cpf.addEventListener("blur", () => {
  warnInvalidCpfOnBlur();
});
elements.phone.addEventListener("input", () => {
  elements.phone.value = maskPhone(elements.phone.value);
});

bootstrap();
