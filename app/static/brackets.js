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
      <p class="ibjjf-kicker">Colliseum Federation</p>
      <h2>${categoryLabel(bracket.category)}</h2>
      <span>${summary.join(" | ")}</span>
    </div>
    <div class="ibjjf-board" data-role="bracketBody"></div>
  `;

  const body = sheet.querySelector('[data-role="bracketBody"]');
  if (bracket.rounds >= 4) {
    body.classList.add("split-brackets");
    body.append(buildBracketHalf(bracket, 1, 1, bracket.bracket_size / 2));
    body.append(buildBracketHalf(bracket, 2, bracket.bracket_size / 2 + 1, bracket.bracket_size));
    body.append(buildFinalsBlock(bracket));
    return sheet;
  }

  body.append(buildCompactBracket(bracket));
  return sheet;
}

function buildCompactBracket(bracket) {
  const compact = document.createElement("div");
  compact.className = "ibjjf-compact-board";
  const halfSize = bracket.bracket_size / 2;
  const sideAMatches = bracket.matches.filter(
    (match) => match.round_number < bracket.rounds && match.position_end <= halfSize,
  );
  const sideBMatches = bracket.matches.filter(
    (match) => match.round_number < bracket.rounds && match.position_start > halfSize,
  );
  const finalMatch = bracket.matches.find((match) => match.round_number === bracket.rounds);

  compact.append(buildBracketSide("Lado A", `Posicoes 1-${halfSize}`, sideAMatches, bracket.rounds, "left"));
  compact.append(buildFinalSection(finalMatch, "Final"));
  compact.append(
    buildBracketSide(
      "Lado B",
      `Posicoes ${halfSize + 1}-${bracket.bracket_size}`,
      sideBMatches,
      bracket.rounds,
      "right",
    ),
  );

  return compact;
}

function buildBracketHalf(bracket, index, startPosition, endPosition) {
  const block = document.createElement("section");
  block.className = "ibjjf-bracket-block";
  const middlePosition = startPosition + (endPosition - startPosition + 1) / 2 - 1;
  const blockFinalRound = bracket.rounds - 1;
  const leftMatches = bracket.matches.filter(
    (match) =>
      match.round_number < blockFinalRound &&
      match.position_start >= startPosition &&
      match.position_end <= middlePosition,
  );
  const rightMatches = bracket.matches.filter(
    (match) =>
      match.round_number < blockFinalRound &&
      match.position_start > middlePosition &&
      match.position_end <= endPosition,
  );
  const blockFinal = bracket.matches.find(
    (match) =>
      match.round_number === blockFinalRound &&
      match.position_start >= startPosition &&
      match.position_end <= endPosition,
  );

  block.innerHTML = `
    <div class="ibjjf-bracket-block-title">BRACKET ${index}/2</div>
    <div class="ibjjf-compact-board" data-role="blockBody"></div>
  `;

  const blockBody = block.querySelector('[data-role="blockBody"]');
  blockBody.append(
    buildBracketSide(
      `Lado ${index}A`,
      `Posicoes ${startPosition}-${middlePosition}`,
      leftMatches,
      bracket.rounds,
      "left",
    ),
  );
  blockBody.append(buildFinalSection(blockFinal, "Final do bracket"));
  blockBody.append(
    buildBracketSide(
      `Lado ${index}B`,
      `Posicoes ${middlePosition + 1}-${endPosition}`,
      rightMatches,
      bracket.rounds,
      "right",
    ),
  );

  return block;
}

function buildFinalsBlock(bracket) {
  const finals = document.createElement("section");
  finals.className = "ibjjf-finals-block";
  const finalMatch = bracket.matches.find((match) => match.round_number === bracket.rounds);
  finals.innerHTML = `
    <div class="ibjjf-bracket-block-title">FINALS</div>
    <div class="ibjjf-finals-center" data-role="finalsCenter"></div>
  `;

  const finalsCenter = finals.querySelector('[data-role="finalsCenter"]');
  finalsCenter.append(buildFinalSection(finalMatch, "Final"));
  return finals;
}

function buildBracketSide(title, subtitle, matches, totalRounds, direction) {
  const side = document.createElement("section");
  side.className = `ibjjf-side ${direction}`;
  side.innerHTML = `
    <div class="ibjjf-side-header">
      <strong>${title}</strong>
      <span>${subtitle}</span>
    </div>
    <div class="ibjjf-rounds"></div>
  `;

  const rounds = side.querySelector(".ibjjf-rounds");
  const groupedMatches = new Map();
  for (const match of matches) {
    if (!groupedMatches.has(match.round_number)) {
      groupedMatches.set(match.round_number, []);
    }
    groupedMatches.get(match.round_number).push(match);
  }

  const orderedRounds = [...groupedMatches.entries()].sort(([left], [right]) =>
    direction === "right" ? right - left : left - right,
  );
  for (const [roundNumber, roundMatches] of orderedRounds) {
    roundMatches.sort((left, right) => left.match_number - right.match_number);
    rounds.append(buildRoundColumn(roundNumber, totalRounds, roundMatches, direction));
  }

  return side;
}

function buildRoundColumn(roundNumber, totalRounds, matches, direction) {
  const round = document.createElement("section");
  round.className = `ibjjf-round ${direction}`;
  round.innerHTML = `
    <div class="ibjjf-round-title">
      <strong>${roundLabel(roundNumber, totalRounds)}</strong>
      <span>${matches.length} luta(s)</span>
    </div>
    <div class="ibjjf-match-list"></div>
  `;

  const matchList = round.querySelector(".ibjjf-match-list");
  for (const match of matches) {
    matchList.append(buildMatchCard(match, roundNumber === 1, direction));
  }

  return round;
}

function buildFinalSection(match, title = "Final") {
  const final = document.createElement("section");
  final.className = "ibjjf-final-section";
  final.innerHTML = `
    <div class="ibjjf-side-header final-header">
      <strong>${title}</strong>
      <span>Vencedor do Lado A x Vencedor do Lado B</span>
    </div>
    <div class="ibjjf-final-match"></div>
  `;

  const finalMatch = final.querySelector(".ibjjf-final-match");
  if (match) {
    finalMatch.append(buildMatchCard(match, false, "final"));
  }

  return final;
}

function buildMatchCard(match, isOpeningRound, direction) {
  const card = document.createElement("article");
  card.className = `ibjjf-match ${direction} ${isOpeningRound ? "opening-round" : ""}`.trim();
  const left = athleteLabel(match.athlete_a);
  const right = athleteLabel(match.athlete_b);
  const statusText = match.status === "bye" ? "BYE" : `Luta ${match.match_number}`;

  card.innerHTML = `
    <div class="ibjjf-match-meta">
      <strong>${statusText}</strong>
      <span>Mat 10</span>
    </div>
    <div class="ibjjf-slot winner">
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
