const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  teamForm: document.querySelector("#teamForm"),
  teamName: document.querySelector("#teamName"),
  teamCreatedDate: document.querySelector("#teamCreatedDate"),
  teamResponsible: document.querySelector("#teamResponsible"),
  teamPhone: document.querySelector("#teamPhone"),
  teamFormStatus: document.querySelector("#teamFormStatus"),
  teamFormMessage: document.querySelector("#teamFormMessage"),
  teamSubmitButton: document.querySelector("#teamSubmitButton"),
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setTeamMessage(text, type = "") {
  elements.teamFormMessage.textContent = text;
  elements.teamFormMessage.className = `message ${type}`.trim();
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

function populateResponsibleBlackBelts(athletes) {
  elements.teamResponsible.innerHTML = "";

  if (!athletes.length) {
    elements.teamResponsible.add(new Option("Nenhum faixa preta cadastrado", ""));
    elements.teamResponsible.disabled = true;
    elements.teamSubmitButton.disabled = true;
    elements.teamFormStatus.textContent = "Responsavel indisponivel";
    setTeamMessage("Cadastre primeiro um atleta faixa preta para vincular como responsavel.", "error");
    return;
  }

  elements.teamResponsible.add(new Option("Selecione o responsavel", ""));
  const sortedAthletes = [...athletes].sort((left, right) => left.name.localeCompare(right.name));
  for (const athlete of sortedAthletes) {
    elements.teamResponsible.add(new Option(athlete.name, athlete.name));
  }

  elements.teamResponsible.disabled = false;
  elements.teamSubmitButton.disabled = false;
  elements.teamFormStatus.textContent = `Faixas pretas: ${athletes.length}`;
  setTeamMessage("");
}

async function loadResponsibleBlackBelts() {
  elements.teamResponsible.disabled = true;
  elements.teamSubmitButton.disabled = true;
  elements.teamResponsible.innerHTML = '<option value="">Carregando faixas pretas...</option>';
  const page = await fetchJson("/athletes?belt=black&limit=100&offset=0");
  populateResponsibleBlackBelts(page.items);
}

function buildTeamPayload() {
  return {
    name: elements.teamName.value.trim(),
    created_date: elements.teamCreatedDate.value,
    responsible: elements.teamResponsible.value,
    phone: elements.teamPhone.value.trim(),
  };
}

async function submitTeam(event) {
  event.preventDefault();
  setTeamMessage("");

  if (!elements.teamForm.reportValidity()) {
    return;
  }

  elements.teamSubmitButton.disabled = true;
  try {
    const team = await fetchJson("/teams", {
      method: "POST",
      body: JSON.stringify(buildTeamPayload()),
    });
    setTeamMessage(`Equipe ${team.name} cadastrada com sucesso.`, "success");
    elements.teamForm.reset();
    await loadResponsibleBlackBelts();
  } catch (error) {
    setTeamMessage(error.message, "error");
  } finally {
    elements.teamSubmitButton.disabled = false;
  }
}

function maskTeamPhone(value) {
  return value
    .replace(/\D/g, "")
    .slice(0, 11)
    .replace(/(\d{2})(\d)/, "$1-$2")
    .replace(/(\d{5})(\d{1,4})$/, "$1-$2");
}

async function bootstrap() {
  try {
    await fetchJson("/health");
    setStatus("Online", true);
    await loadResponsibleBlackBelts();
  } catch (error) {
    setStatus("Offline", false);
    setTeamMessage(error.message, "error");
  }
}

elements.teamForm.addEventListener("submit", submitTeam);
elements.teamPhone.addEventListener("input", () => {
  elements.teamPhone.value = maskTeamPhone(elements.teamPhone.value);
});

bootstrap();
