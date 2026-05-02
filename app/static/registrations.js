const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  registrationForm: document.querySelector("#registrationForm"),
  registrationCompetition: document.querySelector("#registrationCompetition"),
  registrationCpf: document.querySelector("#registrationCpf"),
  registrationBirthDate: document.querySelector("#registrationBirthDate"),
  registrationAthleteName: document.querySelector("#registrationAthleteName"),
  registrationCategory: document.querySelector("#registrationCategory"),
  registrationStatus: document.querySelector("#registrationStatus"),
  registrationMessage: document.querySelector("#registrationMessage"),
  registrationSubmitButton: document.querySelector("#registrationSubmitButton"),
};

const state = {
  competitions: [],
  verifiedAthlete: null,
  verifyToken: 0,
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setMessage(text, type = "") {
  elements.registrationMessage.textContent = text;
  elements.registrationMessage.className = `message ${type}`.trim();
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

function categoryLabel(category) {
  return `${category.age_group} | ${category.belt} | ${category.weight_class}`;
}

function fillCompetitionSelect() {
  elements.registrationCompetition.innerHTML = "";

  if (!state.competitions.length) {
    elements.registrationCompetition.add(new Option("Nenhuma competicao disponivel", ""));
    elements.registrationCompetition.disabled = true;
    return;
  }

  elements.registrationCompetition.add(new Option("Selecione a competicao", ""));
  for (const competition of state.competitions) {
    elements.registrationCompetition.add(new Option(competition.name, String(competition.id)));
  }
  elements.registrationCompetition.disabled = false;
}

function resetVerifiedAthlete(message = "Informe CPF e nascimento") {
  state.verifiedAthlete = null;
  elements.registrationAthleteName.value = "";
  elements.registrationAthleteName.placeholder = message;
  elements.registrationCategory.innerHTML = '<option value="">Categoria calculada apos validacao</option>';
  elements.registrationCategory.disabled = true;
  elements.registrationSubmitButton.disabled = true;
}

function fillEligibleCategories(categories) {
  elements.registrationCategory.innerHTML = "";

  if (!categories.length) {
    elements.registrationCategory.add(new Option("Nenhuma categoria IBJJF compativel", ""));
    elements.registrationCategory.disabled = true;
    elements.registrationSubmitButton.disabled = true;
    return;
  }

  elements.registrationCategory.add(new Option("Selecione a categoria", ""));
  for (const category of categories) {
    elements.registrationCategory.add(new Option(categoryLabel(category), String(category.id)));
  }
  elements.registrationCategory.disabled = false;
  elements.registrationSubmitButton.disabled = false;
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

async function verifyAthleteAndLoadCategories() {
  const competitionId = elements.registrationCompetition.value;
  const cpf = normalizeCpf(elements.registrationCpf.value);
  const birthDate = elements.registrationBirthDate.value;
  const token = ++state.verifyToken;

  resetVerifiedAthlete("Validando atleta...");
  setMessage("");

  if (!competitionId || cpf.length !== 11 || !birthDate) {
    resetVerifiedAthlete();
    elements.registrationStatus.textContent = "Informe competicao, CPF e nascimento";
    return;
  }

  try {
    const options = await fetchJson(
      `/competitions/${competitionId}/registration-options?cpf=${encodeURIComponent(cpf)}&birth_date=${birthDate}`,
    );

    if (token !== state.verifyToken) {
      return;
    }

    state.verifiedAthlete = options.athlete;
    elements.registrationAthleteName.value =
      `${options.athlete.name} | ${options.athlete.team.name} | ${options.athlete.belt}`;
    elements.registrationStatus.textContent = `${options.age_group} | ${options.age} anos`;
    fillEligibleCategories(options.categories);
    if (!options.categories.length) {
      setMessage("Nenhuma categoria IBJJF cadastrada para idade, sexo e faixa deste atleta.", "error");
    }
  } catch (error) {
    if (token !== state.verifyToken) {
      return;
    }
    resetVerifiedAthlete("Atleta nao validado");
    elements.registrationStatus.textContent = "Dados nao conferem";
    setMessage(error.message, "error");
  }
}

async function loadInitialData() {
  state.competitions = await fetchJson("/competitions");
  fillCompetitionSelect();
  resetVerifiedAthlete();
  elements.registrationStatus.textContent = state.competitions.length
    ? "Informe competicao, CPF e nascimento"
    : "Cadastre uma competicao";
}

function buildRegistrationPayload() {
  return {
    cpf: elements.registrationCpf.value.trim(),
    birth_date: elements.registrationBirthDate.value,
    category_id: Number(elements.registrationCategory.value),
  };
}

async function submitRegistration(event) {
  event.preventDefault();
  setMessage("");

  if (!elements.registrationForm.reportValidity()) {
    return;
  }

  if (!state.verifiedAthlete) {
    setMessage("Confirme CPF e data de nascimento antes de inscrever.", "error");
    return;
  }

  elements.registrationSubmitButton.disabled = true;
  try {
    const competitionId = elements.registrationCompetition.value;
    const registration = await fetchJson(`/competitions/${competitionId}/registrations`, {
      method: "POST",
      body: JSON.stringify(buildRegistrationPayload()),
    });
    setMessage(
      `${registration.athlete.name} inscrito em ${categoryLabel(registration.category)}.`,
      "success",
    );
    elements.registrationForm.reset();
    resetVerifiedAthlete();
    fillCompetitionSelect();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.registrationSubmitButton.disabled = false;
  }
}

async function bootstrap() {
  try {
    await fetchJson("/health");
    setStatus("Online", true);
    await loadInitialData();
  } catch (error) {
    setStatus("Offline", false);
    setMessage(error.message, "error");
  }
}

elements.registrationForm.addEventListener("submit", submitRegistration);
elements.registrationCompetition.addEventListener("change", verifyAthleteAndLoadCategories);
elements.registrationCpf.addEventListener("input", () => {
  elements.registrationCpf.value = maskCpf(elements.registrationCpf.value);
});
elements.registrationCpf.addEventListener("blur", verifyAthleteAndLoadCategories);
elements.registrationBirthDate.addEventListener("change", verifyAthleteAndLoadCategories);

bootstrap();
