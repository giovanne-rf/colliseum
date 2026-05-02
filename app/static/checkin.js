const elements = {
  apiStatus: document.querySelector("#apiStatus"),
  competitionSelect: document.querySelector("#competitionSelect"),
  sexFilter: document.querySelector("#sexFilter"),
  beltFilter: document.querySelector("#beltFilter"),
  ageGroupFilter: document.querySelector("#ageGroupFilter"),
  weightFilter: document.querySelector("#weightFilter"),
  checkinSummary: document.querySelector("#checkinSummary"),
  checkinMessage: document.querySelector("#checkinMessage"),
  checkinGroups: document.querySelector("#checkinGroups"),
};

const state = {
  competitions: [],
  registrations: [],
};

const beltLabels = {
  white: "Branca",
  blue: "Azul",
  purple: "Roxa",
  brown: "Marrom",
  black: "Preta",
};

const sexLabels = {
  male: "Masculino",
  female: "Feminino",
};

function setStatus(text, ok = false) {
  elements.apiStatus.textContent = text;
  elements.apiStatus.classList.toggle("ok", ok);
}

function setMessage(text, type = "") {
  elements.checkinMessage.textContent = text;
  elements.checkinMessage.className = `message ${type}`.trim();
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

  return response.status === 204 ? null : response.json();
}

function normalizeText(value) {
  return value || "Nao informado";
}

function groupKey(registration) {
  const athlete = registration.athlete;
  const category = registration.category;
  return [
    athlete.sex,
    category.belt,
    category.age_group,
    category.weight_class,
  ].join("||");
}

function groupTitle(registration) {
  const athlete = registration.athlete;
  const category = registration.category;
  return [
    sexLabels[athlete.sex] || athlete.sex,
    beltLabels[category.belt] || category.belt,
    category.age_group,
    category.weight_class,
  ].join(" | ");
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((left, right) =>
    String(left).localeCompare(String(right), "pt-BR"),
  );
}

function fillSelect(select, values, placeholder, labelFactory = (value) => value) {
  const currentValue = select.value;
  select.innerHTML = "";
  select.add(new Option(placeholder, ""));

  for (const value of values) {
    select.add(new Option(labelFactory(value), value));
  }

  select.disabled = false;
  select.value = values.includes(currentValue) ? currentValue : "";
}

function fillCompetitionSelect() {
  elements.competitionSelect.innerHTML = "";

  if (!state.competitions.length) {
    elements.competitionSelect.add(new Option("Nenhuma competicao cadastrada", ""));
    elements.competitionSelect.disabled = true;
    return;
  }

  elements.competitionSelect.add(new Option("Selecione a competicao", ""));
  for (const competition of state.competitions) {
    elements.competitionSelect.add(new Option(competition.name, String(competition.id)));
  }
  elements.competitionSelect.disabled = false;
}

function updateFilters() {
  const registrations = state.registrations;
  const selectedSex = elements.sexFilter.value;
  const selectedBelt = elements.beltFilter.value;
  const selectedAgeGroup = elements.ageGroupFilter.value;
  const selectedWeight = elements.weightFilter.value;

  fillSelect(
    elements.sexFilter,
    uniqueSorted(registrations.map((item) => item.athlete.sex)),
    "Todos",
    (value) => sexLabels[value] || value,
  );
  fillSelect(
    elements.beltFilter,
    uniqueSorted(registrations.map((item) => item.category.belt)),
    "Todas",
    (value) => beltLabels[value] || value,
  );
  fillSelect(
    elements.ageGroupFilter,
    uniqueSorted(registrations.map((item) => item.category.age_group)),
    "Todas",
  );
  fillSelect(
    elements.weightFilter,
    uniqueSorted(registrations.map((item) => item.category.weight_class)),
    "Todos",
  );

  elements.sexFilter.value = selectedSex;
  elements.beltFilter.value = selectedBelt;
  elements.ageGroupFilter.value = selectedAgeGroup;
  elements.weightFilter.value = selectedWeight;
}

function filteredRegistrations() {
  return state.registrations.filter((registration) => {
    const athlete = registration.athlete;
    const category = registration.category;
    return (
      (!elements.sexFilter.value || athlete.sex === elements.sexFilter.value) &&
      (!elements.beltFilter.value || category.belt === elements.beltFilter.value) &&
      (!elements.ageGroupFilter.value || category.age_group === elements.ageGroupFilter.value) &&
      (!elements.weightFilter.value || category.weight_class === elements.weightFilter.value)
    );
  });
}

function renderGroups() {
  const registrations = filteredRegistrations();
  elements.checkinGroups.innerHTML = "";
  elements.checkinSummary.textContent =
    `${registrations.length} atleta(s) exibido(s) de ${state.registrations.length} inscrito(s)`;

  if (!state.registrations.length) {
    elements.checkinGroups.innerHTML = '<div class="empty">Nenhum atleta inscrito nesta competicao.</div>';
    return;
  }

  if (!registrations.length) {
    elements.checkinGroups.innerHTML = '<div class="empty">Nenhum atleta encontrado para os filtros selecionados.</div>';
    return;
  }

  const groups = new Map();
  for (const registration of registrations) {
    const key = groupKey(registration);
    if (!groups.has(key)) {
      groups.set(key, {
        title: groupTitle(registration),
        items: [],
      });
    }
    groups.get(key).items.push(registration);
  }

  const orderedGroups = [...groups.values()].sort((left, right) =>
    left.title.localeCompare(right.title, "pt-BR"),
  );

  for (const group of orderedGroups) {
    group.items.sort((left, right) => left.athlete.name.localeCompare(right.athlete.name, "pt-BR"));

    const section = document.createElement("section");
    section.className = "checkin-group";
    section.innerHTML = `
      <div class="checkin-group-heading">
        <h2>${group.title}</h2>
        <span>${group.items.length} atleta(s)</span>
      </div>
      <div class="checkin-table-wrap">
        <table class="checkin-table">
          <thead>
            <tr>
              <th>Atleta</th>
              <th>Equipe</th>
              <th>CPF</th>
              <th>Nascimento</th>
              <th>Inscricao</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    `;

    const tbody = section.querySelector("tbody");
    for (const registration of group.items) {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${registration.athlete.name}</td>
        <td>${normalizeText(registration.athlete.team?.name)}</td>
        <td>${registration.athlete.cpf}</td>
        <td>${registration.athlete.birth_date}</td>
        <td>#${registration.id}</td>
      `;
      tbody.append(row);
    }

    elements.checkinGroups.append(section);
  }
}

async function loadRegistrations() {
  const competitionId = elements.competitionSelect.value;
  state.registrations = [];
  setMessage("");

  if (!competitionId) {
    elements.checkinSummary.textContent = "Selecione uma competicao";
    elements.checkinGroups.innerHTML = '<div class="empty">Nenhuma competicao selecionada.</div>';
    return;
  }

  elements.checkinSummary.textContent = "Carregando inscricoes...";
  try {
    state.registrations = await fetchJson(`/competitions/${competitionId}/registrations`);
    updateFilters();
    renderGroups();
  } catch (error) {
    setMessage(error.message, "error");
    elements.checkinSummary.textContent = "Falha ao carregar";
    elements.checkinGroups.innerHTML = '<div class="empty">Nao foi possivel carregar as inscricoes.</div>';
  }
}

async function bootstrap() {
  try {
    await fetchJson("/health");
    setStatus("Online", true);
    state.competitions = await fetchJson("/competitions");
    fillCompetitionSelect();
  } catch (error) {
    setStatus("Offline", false);
    setMessage(error.message, "error");
  }
}

elements.competitionSelect.addEventListener("change", loadRegistrations);
elements.sexFilter.addEventListener("change", renderGroups);
elements.beltFilter.addEventListener("change", renderGroups);
elements.ageGroupFilter.addEventListener("change", renderGroups);
elements.weightFilter.addEventListener("change", renderGroups);

bootstrap();
