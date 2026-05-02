const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  competitionForm: document.querySelector("#competitionForm"),
  competitionName: document.querySelector("#competitionName"),
  competitionDate: document.querySelector("#competitionDate"),
  competitionStatus: document.querySelector("#competitionStatus"),
  competitionMessage: document.querySelector("#competitionMessage"),
  competitionSubmitButton: document.querySelector("#competitionSubmitButton"),
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setMessage(text, type = "") {
  elements.competitionMessage.textContent = text;
  elements.competitionMessage.className = `message ${type}`.trim();
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

async function loadCompetitionCount() {
  const competitions = await fetchJson("/competitions");
  elements.competitionStatus.textContent = `Competicoes: ${competitions.length}`;
}

function buildCompetitionPayload() {
  return {
    name: elements.competitionName.value.trim(),
    event_date: elements.competitionDate.value,
  };
}

async function submitCompetition(event) {
  event.preventDefault();
  setMessage("");

  if (!elements.competitionForm.reportValidity()) {
    return;
  }

  elements.competitionSubmitButton.disabled = true;
  try {
    const competition = await fetchJson("/competitions", {
      method: "POST",
      body: JSON.stringify(buildCompetitionPayload()),
    });
    setMessage(`Competicao ${competition.name} cadastrada.`, "success");
    elements.competitionForm.reset();
    await loadCompetitionCount();
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.competitionSubmitButton.disabled = false;
  }
}

async function bootstrap() {
  try {
    await fetchJson("/health");
    setStatus("Online", true);
    await loadCompetitionCount();
  } catch (error) {
    setStatus("Offline", false);
    setMessage(error.message, "error");
  }
}

elements.competitionForm.addEventListener("submit", submitCompetition);

bootstrap();
