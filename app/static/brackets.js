const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  bracketForm: document.querySelector("#bracketForm"),
  bracketCompetition: document.querySelector("#bracketCompetition"),
  bracketStatus: document.querySelector("#bracketStatus"),
  bracketMessage: document.querySelector("#bracketMessage"),
  bracketSubmitButton: document.querySelector("#bracketSubmitButton"),
  bracketResult: document.querySelector("#bracketResult"),
  bracketSummary: document.querySelector("#bracketSummary"),
  bracketGroups: document.querySelector("#bracketGroups"),
};

const state = {
  competitions: [],
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setMessage(text, type = "") {
  elements.bracketMessage.textContent = text;
  elements.bracketMessage.className = `message ${type}`.trim();
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

function roundLabel(roundNumber, totalRounds) {
  const roundsFromFinal = totalRounds - roundNumber;
  if (roundsFromFinal === 0) {
    return "Final";
  }
  if (roundsFromFinal === 1) {
    return "Semifinal";
  }
  if (roundsFromFinal === 2) {
    return "Quartas";
  }
  return `Rodada ${roundNumber}`;
}

function athleteLabel(athlete) {
  if (!athlete) {
    return {
      name: "A definir",
      team: "",
    };
  }

  return {
    name: athlete.name,
    team: athlete.team?.name || "Sem equipe",
  };
}

function fillSelect(select, items, placeholder, labelFactory) {
  select.innerHTML = "";

  if (!items.length) {
    select.add(new Option("Nenhum registro disponivel", ""));
    select.disabled = true;
    return;
  }

  select.add(new Option(placeholder, ""));
  for (const item of items) {
    select.add(new Option(labelFactory(item), String(item.id)));
  }
  select.disabled = false;
}

function populateForm() {
  fillSelect(
    elements.bracketCompetition,
    state.competitions,
    "Selecione a competicao",
    (competition) => competition.name,
  );

  const ready = state.competitions.length;
  elements.bracketSubmitButton.disabled = !ready;
  elements.bracketStatus.textContent = ready
    ? "Formato IBJJF por categoria"
    : "Cadastre uma competicao";
}

async function loadInitialData() {
  state.competitions = await fetchJson("/competitions");
  populateForm();
}

function buildBracketPayload() {
  return {
    replace_existing: true,
  };
}

async function submitBracket(event) {
  event.preventDefault();
  setMessage("");

  if (!elements.bracketForm.reportValidity()) {
    return;
  }

  elements.bracketSubmitButton.disabled = true;
  try {
    const competitionId = elements.bracketCompetition.value;
    const result = await fetchJson(`/competitions/${competitionId}/brackets/generate-all`, {
      method: "POST",
      body: JSON.stringify(buildBracketPayload()),
    });
    setMessage("Chaves geradas com sucesso.", "success");
    renderBrackets(result);
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    elements.bracketSubmitButton.disabled = false;
  }
}

function renderBrackets(result) {
  elements.bracketResult.hidden = false;
  elements.bracketSummary.textContent = `${result.generated_count} chave(s) gerada(s)`;
  if (result.skipped_count) {
    elements.bracketSummary.textContent += ` | ${result.skipped_count} categoria(s) sem minimo`;
  }

  elements.bracketGroups.innerHTML = "";
  for (const bracket of result.brackets) {
    elements.bracketGroups.append(buildBracketGroup(bracket));
  }
}

function buildBracketGroup(bracket) {
  const sheet = document.createElement("section");
  sheet.className = "ibjjf-sheet";
  const summary = [
    `${bracket.bracket_size} posicoes`,
    `${bracket.bye_count} byes`,
    `${bracket.rounds} rodadas`,
  ];
  if (bracket.same_team_conflicts) {
    summary.push(`${bracket.same_team_conflicts} conflito(s) inevitavel(is)`);
  }

  sheet.innerHTML = `
    <div class="ibjjf-sheet-header">
      <div>
        <p class="ibjjf-kicker">Colliseum Federation</p>
        <h2>${categoryLabel(bracket.category)}</h2>
      </div>
      <span>${summary.join(" | ")}</span>
    </div>
    <div class="ibjjf-rounds" data-role="rounds"></div>
  `;

  const rounds = sheet.querySelector('[data-role="rounds"]');
  const groupedMatches = new Map();

  for (const match of bracket.matches) {
    if (!groupedMatches.has(match.round_number)) {
      groupedMatches.set(match.round_number, []);
    }
    groupedMatches.get(match.round_number).push(match);
  }

  const orderedRounds = [...groupedMatches.entries()].sort(([left], [right]) => left - right);
  for (const [roundNumber, matches] of orderedRounds) {
    matches.sort((left, right) => left.match_number - right.match_number);
    const round = document.createElement("section");
    round.className = "ibjjf-round";
    round.innerHTML = `
      <div class="ibjjf-round-title">
        <strong>${roundLabel(roundNumber, bracket.rounds)}</strong>
        <span>${matches.length} luta(s)</span>
      </div>
      <div class="ibjjf-match-list"></div>
    `;

    const matchList = round.querySelector(".ibjjf-match-list");
    for (const match of matches) {
      matchList.append(buildMatchCard(match, roundNumber === 1));
    }
    rounds.append(round);
  }

  return sheet;
}

function buildMatchCard(match, isOpeningRound) {
  const card = document.createElement("article");
  card.className = `ibjjf-match ${isOpeningRound ? "opening-round" : ""}`.trim();
  const left = athleteLabel(match.athlete_a);
  const right = athleteLabel(match.athlete_b);
  const statusText = match.status === "bye" ? "BYE" : `Luta ${match.match_number}`;

  card.innerHTML = `
    <div class="ibjjf-match-meta">${statusText}</div>
    <div class="ibjjf-slot">
      <span class="ibjjf-position">${match.position_start}</span>
      <div>
        <strong>${left.name}</strong>
        <small>${left.team}</small>
      </div>
    </div>
    <div class="ibjjf-slot">
      <span class="ibjjf-position">${match.position_end}</span>
      <div>
        <strong>${right.name}</strong>
        <small>${right.team}</small>
      </div>
    </div>
  `;

  return card;
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

elements.bracketForm.addEventListener("submit", submitBracket);

bootstrap();
