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
  reloadTeams: document.querySelector("#reloadTeams"),
  teamList: document.querySelector("#teamList"),
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

function renderTeams(items) {
  elements.teamList.innerHTML = "";

  if (!items.length) {
    elements.teamList.innerHTML = '<div class="empty">Nenhuma equipe encontrada</div>';
    elements.teamFormStatus.textContent = "Equipes: 0";
    return;
  }

  const sortedTeams = [...items].sort((left, right) => left.name.localeCompare(right.name));
  for (const team of sortedTeams) {
    const card = document.createElement("article");
    card.className = "team-card";
    card.innerHTML = `
      <strong>${team.name}</strong>
      <dl>
        <dt>ID</dt><dd>${team.id}</dd>
        <dt>Criacao</dt><dd>${team.created_date}</dd>
        <dt>Responsavel</dt><dd>${team.responsible}</dd>
        <dt>Telefone</dt><dd>${team.phone}</dd>
      </dl>
    `;
    elements.teamList.append(card);
  }

  elements.teamFormStatus.textContent = `Equipes: ${items.length}`;
}

async function loadTeams() {
  const page = await fetchJson("/teams?limit=100&offset=0");
  renderTeams(page.items);
}

function buildTeamPayload() {
  return {
    name: elements.teamName.value.trim(),
    created_date: elements.teamCreatedDate.value,
    responsible: elements.teamResponsible.value.trim(),
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
    await loadTeams();
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
    await loadTeams();
  } catch (error) {
    setStatus("Offline", false);
    setTeamMessage(error.message, "error");
  }
}

elements.teamForm.addEventListener("submit", submitTeam);
elements.reloadTeams.addEventListener("click", loadTeams);
elements.teamPhone.addEventListener("input", () => {
  elements.teamPhone.value = maskTeamPhone(elements.teamPhone.value);
});

bootstrap();
