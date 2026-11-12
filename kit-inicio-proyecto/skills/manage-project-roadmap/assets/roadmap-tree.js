(() => {
  "use strict";
  let data = JSON.parse(document.getElementById("roadmap-data").textContent);
  const $ = (id) => document.getElementById(id);
  const labels = {PENDIENTE: "Pendiente", EN_CURSO: "En curso", PARCIAL: "Parcial", HECHO: "Hecho", BLOQUEADO: "Bloqueado", EXCLUIDO: "Fuera del alcance"};
  const scopes = {SOLICITADO: "Solicitado", PROPUESTO: "Propuesto", EXCLUIDO: "Excluido"};
  const scopeDescriptions = {SOLICITADO: "Pedido confirmado por el usuario.", PROPUESTO: "Propuesta pendiente de autorización para ejecutarse.", EXCLUIDO: "Fuera del alcance por una decisión explícita."};
  const fieldLabel = (name) => name === "Capa" ? "Alcance autorizado" : name === "Alcance" ? "Descripción y alcance" : name;
  const colors = Object.fromEntries(Object.keys(labels).map((status) => [status, `var(--color-${status})`]));
  const backgrounds = Object.fromEntries(Object.keys(labels).map((status) => [status, `var(--background-${status})`]));
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");
  let themePreference = null;
  try {
    const saved = localStorage.getItem("roadmap-theme");
    if (saved === "light" || saved === "dark") themePreference = saved;
  } catch {} // El visor también funciona si el navegador bloquea el almacenamiento.
  function applyTheme() {
    const dark = themePreference ? themePreference === "dark" : systemTheme.matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    $("theme-toggle").setAttribute("aria-pressed", String(dark));
  }
  $("theme-toggle").addEventListener("click", () => {
    themePreference = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {localStorage.setItem("roadmap-theme", themePreference);} catch {}
    applyTheme();
  });
  systemTheme.addEventListener?.("change", () => {if (!themePreference) applyTheme();});
  applyTheme();
  function colorize(node, status) {
    node.style.setProperty("--status", colors[status]);
    node.style.setProperty("--status-bg", backgrounds[status]);
  }
  const tasks = new Map(data.tasks.map((task) => [task.id, task]));
  const dependents = new Map(data.tasks.map((task) => [task.id, []]));
  data.edges.forEach((edge) => dependents.get(edge.from).push(edge.to));
  const states = new Set(data.states);
  const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const viewport = $("viewport");
  let selected = null, chain = null, visible = [], positions = new Map(), imageIndex = 0, stepImage = () => {};
  let entering = new Set(), changed = new Set(), detailTask = null;
  const motionClasses = (node, id) => {node.classList.toggle("enter", entering.has(id)); node.classList.toggle("changed", changed.has(id));};
  const slide = (node, delta) => {
    if (typeof node.animate === "function" && matchMedia("(prefers-reduced-motion: no-preference)").matches) node.animate([{opacity: 0, transform: `translateX(${delta * 12}px)`}, {opacity: 1, transform: "none"}], {duration: 200, easing: "cubic-bezier(.2,0,0,1)"});
  };
  let scale = 1, pan = {x: 0, y: 0}, bounds = {width: 1, height: 1}, drag = null;
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const dot = (status) => {const node = element("span", undefined, "dot"); node.style.setProperty("--status", colors[status]); node.setAttribute("aria-hidden", "true"); return node;};
  const drafts = new Map(), instructions = new Map(), proposalInstructions = new Map();
  let actionTask = null, actionTrigger = null, actionBusy = false;
  const promptFor = (id, instruction = "", proposed = null) => RoadmapContext.buildPrompt(data, id, instruction, proposed);
  const canPersist = () => Boolean(data.live?.allowEdit && location.protocol === "http:" && ["127.0.0.1", "localhost"].includes(location.hostname));
  function notice(message) {
    $("action-notice").textContent = message; $("action-notice").hidden = false;
  }
  function codexLink(taskId, getPrompt = () => promptFor(taskId)) {
    const url = RoadmapContext.codexProjectUrl(data, getPrompt());
    if (!url) {
      const unavailable = element("button", "Abrir Codex"); unavailable.type = "button"; unavailable.disabled = true;
      unavailable.title = "Regenerá el visor desde el proyecto para incluir su carpeta local.";
      return unavailable;
    }
    const link = element("a", "Abrir Codex", "action-link");
    link.href = url; link.title = `Abrir ${data.projectName} en Codex: ${data.projectPath}`;
    link.addEventListener("click", () => notice(`Se solicitó abrir Codex en ${data.projectPath} con el contexto de ${taskId}. Revisá el mensaje antes de enviarlo.`));
    return link;
  }
  async function copyText(text, fallback) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text); notice("Contexto copiado. Pegalo en Codex para continuar.");
    } catch {
      if (fallback) {fallback.focus(); fallback.select(); notice("Seleccionamos el prompt. Usá Ctrl+C o ⌘+C para copiarlo.");}
      else openInstruction(actionTask || selected, text);
    }
  }
  function openAction(taskId, title) {
    if (!$("task-action").open) actionTrigger = document.activeElement;
    actionTask = taskId;
    $("action-title").textContent = `${title} · ${taskId}`;
    $("action-body").replaceChildren(); $("action-footer").replaceChildren();
    if (!$("task-action").open) $("task-action").showModal();
  }
  function closeAction() {
    if (actionBusy) return;
    $("task-action").close(); actionTask = null;
    (actionTrigger?.isConnected ? actionTrigger : $("detail").querySelector("button") || $("search")).focus({preventScroll: true});
  }
  $("action-close").addEventListener("click", closeAction);
  $("task-action").addEventListener("cancel", (event) => {event.preventDefault(); closeAction();});
  function labeledInput(label, value, multiline = true) {
    const wrapper = element("label", label, "action-field"), input = element(multiline ? "textarea" : "input");
    input.value = value; input.required = true;
    if (multiline) input.rows = label.includes("Prompt") ? 14 : 3;
    wrapper.append(input); return {wrapper, input};
  }
  function openInstruction(taskId, fallbackText = null, proposed = null, initialInstruction = "", fromEditor = false) {
    if (!tasks.has(taskId)) {notice("La tarea ya no existe. Actualizá la selección."); return;}
    openAction(taskId, "Dar instrucción a Codex");
    const task = tasks.get(taskId);
    $("action-body").append(element("p", `${task.title} · ${labels[task.status]}`));
    const instructionValue = proposed ? (proposalInstructions.get(taskId) ?? initialInstruction) : (initialInstruction || instructions.get(taskId) || "");
    const instruction = labeledInput("Instrucción adicional", instructionValue); instruction.input.required = false;
    const preview = labeledInput("Prompt para copiar", proposed ? promptFor(taskId, instructionValue, proposed) : (fallbackText || promptFor(taskId, instructionValue)));
    preview.input.readOnly = true;
    $("action-body").append(instruction.wrapper, preview.wrapper,
      element("p", `Abrir Codex prepara este prompt en un chat local en ${data.projectPath || "la carpeta del proyecto (regenerá el visor para identificarla)"}; revisalo y envialo desde la app. Si el navegador no abre Codex, copiá el prompt y pegalo en el proyecto.`));
    const openCodex = codexLink(taskId, () => preview.input.value);
    instruction.input.addEventListener("input", () => {
      (proposed ? proposalInstructions : instructions).set(taskId, instruction.input.value);
      preview.input.value = promptFor(taskId, instruction.input.value, proposed);
      if (openCodex.tagName === "A") openCodex.href = RoadmapContext.codexProjectUrl(data, preview.input.value);
    });
    const copy = element("button", "Copiar prompt"); copy.type = "button";
    copy.addEventListener("click", () => copyText(preview.input.value, preview.input));
    const back = element("button", fromEditor ? "Volver al formulario" : "Volver al detalle"); back.type = "button";
    back.addEventListener("click", () => fromEditor && tasks.has(taskId) ? openEditor(taskId) : closeAction());
    $("action-footer").append(back, copy, openCodex);
    instruction.input.focus();
  }
  async function editRequest(operation, payload) {
    if (!canPersist()) throw new Error("La copia estática y el servidor sin --allow-edit no guardan cambios.");
    const sessionResponse = await fetch("/__roadmap__/session", {cache: "no-store", signal: AbortSignal.timeout(5000)});
    if (!sessionResponse.ok) throw new Error("No se pudo autorizar la sesión local de edición.");
    const session = await sessionResponse.json();
    if (session.projectId !== data.projectId) throw new Error("El servidor corresponde a otro proyecto.");
    const response = await fetch(`/__roadmap__/edit/${operation}`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-Roadmap-Token": session.token},
      body: JSON.stringify(payload), signal: AbortSignal.timeout(15000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function openEditor(taskId) {
    const task = tasks.get(taskId);
    openAction(taskId, "Editar tarea");
    const base = {taskId, revision: data.revision || null};
    const draft = drafts.get(taskId) || {title: task.title, fields: {...task.fields}, revision: base.revision};
    drafts.set(taskId, draft);
    const form = element("form"), message = element("p"); message.setAttribute("role", "status");
    message.textContent = canPersist() ? "Revisá los cambios y autorizá el guardado local. Después revisá git diff y abrí una PR hacia main." : "Modo propuesta: no se escriben archivos. Podés copiar la edición propuesta para revisarla con Codex. Para guardar, iniciá serve --allow-edit en una rama Git.";
    form.append(element("p", `ID: ${task.id} · Estado: ${task.status} · Dependencias: ${task.fields.Dependencias}. Estos datos se conservan. Agregá nuevas verificaciones al final de Evidencia actual para conservar su historia.`), message);
    const title = labeledInput("Título", draft.title, false); title.input.maxLength = 500; form.append(title.wrapper);
    const controls = new Map();
    for (const name of data.fieldNames.filter((name) => name !== "Dependencias")) {
      const control = labeledInput(fieldLabel(name), draft.fields[name]);
      if (name === "Capa") control.wrapper.append(element("span", "Solicitado: pedido confirmado. Propuesto: pendiente de autorización. Excluido: fuera del alcance por decisión explícita."));
      controls.set(name, control.input); form.append(control.wrapper);
    }
    const diff = element("pre", "", "edit-diff"); diff.hidden = true;
    const authorization = element("label", undefined, "edit-authorization"), checkbox = element("input"); checkbox.type = "checkbox"; checkbox.disabled = true;
    authorization.append(checkbox, element("span", "Revisé las diferencias y autorizo guardar este cambio local para revisión mediante Git y Pull Request."));
    authorization.hidden = !canPersist(); form.append(diff, authorization); $("action-body").append(form);
    const back = element("button", "Volver al detalle"), review = element("button", "Validar y revisar cambios"), save = element("button", "Guardar cambio autorizado"), copy = element("button", "Preparar propuesta para Codex");
    for (const button of [back, review, save, copy]) button.type = "button";
    back.addEventListener("click", closeAction);
    review.hidden = save.hidden = !canPersist(); save.disabled = true;
    $("action-footer").append(back, copy, review, save);
    let approval = null, reviewedPayload = null;
    function currentPayload() {
      const fields = Object.fromEntries([...controls].filter(([name, input]) => input.value.trim() !== task.fields[name]).map(([name, input]) => [name, input.value.trim()]));
      return {...base, revision: draft.revision, title: title.input.value.trim(), fields};
    }
    function invalidate() {
      draft.title = title.input.value; draft.fields = Object.fromEntries([...controls].map(([name, input]) => [name, input.value]));
      approval = null; reviewedPayload = null; save.disabled = true; checkbox.checked = false; checkbox.disabled = true; diff.hidden = true;
    }
    form.addEventListener("input", (event) => {if (event.target !== checkbox) invalidate();});
    checkbox.addEventListener("change", () => {save.disabled = !checkbox.checked || !approval;});
    const busy = (value) => {
      actionBusy = value; $("action-close").disabled = value;
      for (const input of [title.input, ...controls.values(), back, review, copy]) input.disabled = value;
      checkbox.disabled = value || !approval; save.disabled = value || !approval || !checkbox.checked;
    };
    review.addEventListener("click", async () => {
      if (!form.reportValidity()) return;
      busy(true);
      try {
        const payload = currentPayload(), result = await editRequest("preview", payload);
        reviewedPayload = payload; approval = result.approval; checkbox.checked = false;
        diff.textContent = result.diff; diff.hidden = false;
        message.textContent = `Plan completo válido. Archivo: ${result.source}. Rama: ${result.branch}. Revisá las diferencias antes de autorizar.`;
        diff.scrollIntoView({block: "nearest"});
      } catch (error) {approval = null; message.textContent = error.message;}
      finally {busy(false);}
    });
    save.addEventListener("click", async () => {
      if (!approval || !checkbox.checked || !reviewedPayload) return;
      busy(true);
      try {
        const result = await editRequest("save", {...reviewedPayload, approval, authorized: true});
        drafts.delete(taskId); proposalInstructions.delete(taskId); busy(false); closeAction(); notice(result.message);
      } catch (error) {approval = null; checkbox.checked = false; message.textContent = error.message;}
      finally {busy(false);}
    });
    copy.addEventListener("click", () => {
      if (!form.reportValidity()) return;
      const proposed = currentPayload();
      const instruction = "Revisá esta propuesta de edición de la tarea. Validá el plan completo y prepará el diff para revisión antes de guardar.";
      openInstruction(taskId, null, proposed, instruction, true);
    });
    form.addEventListener("submit", (event) => event.preventDefault()); title.input.focus();
  }
  function closure(id, direction) {
    const found = new Set([id]), pending = [id];
    while (pending.length) {
      const current = pending.pop();
      const next = direction === "before" ? tasks.get(current).dependencies : dependents.get(current);
      next.forEach((related) => {if (!found.has(related)) {found.add(related); pending.push(related);}});
    }
    return found;
  }
  function chainIds(id) {return new Set([...closure(id, "before"), ...closure(id, "after")]);}
  const fullLevels = new Map();
  function level(id) {
    if (!fullLevels.has(id)) fullLevels.set(id, Math.max(-1, ...tasks.get(id).dependencies.map(level)) + 1);
    return fullLevels.get(id);
  }
  data.tasks.forEach((task) => level(task.id));
  data.states.forEach((status) => {
    const button = element("button", undefined, "state-card");
    button.type = "button";
    colorize(button, status);
    button.dataset.status = status;
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-label", `${labels[status]}: ${data.tasks.filter((task) => task.status === status).length} tareas`);
    button.append(element("span", String(data.tasks.filter((task) => task.status === status).length), "count"), dot(status), element("span", labels[status], "state-name"));
    button.addEventListener("click", () => {states.has(status) ? states.delete(status) : states.add(status); chain = null; render();});
    $("states").append(button);
  });
  data.modules.forEach((module) => {const option = element("option", module.title); option.value = module.id; $("module").append(option);});
  function transform(animated = false) {
    $("scene").classList.toggle("glide", animated);
    $("scene").style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${scale})`;
    $("zoom-label").textContent = `${Math.round(scale * 100)}%`;
  }
  function fit(animated = false) {
    if (!visible.length) return;
    scale = Math.min(1, Math.max(.04, Math.min((viewport.clientWidth - 50) / bounds.width, (viewport.clientHeight - 50) / bounds.height)));
    pan = {x: (viewport.clientWidth - bounds.width * scale) / 2, y: (viewport.clientHeight - bounds.height * scale) / 2};
    transform(animated);
  }
  function readableFrame() {
    fit();
    if (scale < .65) {
      scale = .65;
      pan = {x: 24, y: (viewport.clientHeight - bounds.height * scale) / 2};
      transform();
    }
  }
  function zoom(factor, x, y) {
    // Con coordenadas viene de la rueda, que debe seguir al gesto sin retraso.
    const animated = x === undefined;
    if (animated) {x = viewport.clientWidth / 2; y = viewport.clientHeight / 2;}
    const previous = scale;
    scale = Math.min(2, Math.max(.04, scale * factor));
    pan = {x: x - (x - pan.x) * scale / previous, y: y - (y - pan.y) * scale / previous};
    transform(animated);
  }
  function center(id, animated = false) {
    const position = positions.get(id);
    if (!position) return;
    scale = Math.max(.85, scale);
    pan = {x: viewport.clientWidth / 2 - (position.x + 98) * scale, y: viewport.clientHeight / 2 - (position.y + 53) * scale};
    transform(animated);
  }
  function resetFilters() {
    $("search").value = ""; $("module").value = ""; $("scope").value = "";
    data.states.forEach((status) => states.add(status));
    chain = null;
  }
  function select(id, fromList = false, fromRelation = false) {
    selected = id; imageIndex = 0;
    if (fromRelation) {resetFilters(); render(false);}
    else {paintSelection(); renderDetail();}
    if (fromList || fromRelation) center(id, true);
  }
  function paintSelection() {
    const related = selected ? chainIds(selected) : new Set();
    document.querySelectorAll("[data-task]").forEach((node) => {
      node.classList.toggle("selected", node.dataset.task === selected);
      node.setAttribute("aria-pressed", String(node.dataset.task === selected));
      if (node.classList.contains("node")) node.classList.toggle("related", related.has(node.dataset.task));
    });
    document.querySelectorAll(".edge").forEach((edge) => edge.classList.toggle("related", related.has(edge.dataset.from) && related.has(edge.dataset.to)));
  }
  function drawGraph() {
    positions = new Map();
    $("nodes").replaceChildren(); $("connections").replaceChildren();
    const levels = [...new Set(visible.map((task) => fullLevels.get(task.id)))].sort((a, b) => a - b);
    const columns = levels.map((value) => visible.filter((task) => fullLevels.get(task.id) === value));
    const rows = Math.max(1, ...columns.map((column) => column.length));
    columns.forEach((column, columnIndex) => {
      const averageParent = (task) => {
        const ys = task.dependencies.filter((id) => positions.has(id)).map((id) => positions.get(id).y);
        return ys.length ? ys.reduce((sum, y) => sum + y, 0) / ys.length : 0;
      };
      column.sort((a, b) => averageParent(a) - averageParent(b) || a.id.localeCompare(b.id));
      const heading = element("span", `Nivel ${levels[columnIndex] + 1}`, "level-label");
      heading.style.left = `${columnIndex * 270 + 24}px`; heading.style.top = "10px";
      $("nodes").append(heading);
      column.forEach((task, row) => {
        const position = {x: columnIndex * 270 + 24, y: 44 + row * 134 + (rows - column.length) * 67};
        positions.set(task.id, position);
        const button = element("button", undefined, "node");
        button.dataset.task = task.id;
        button.style.left = `${position.x}px`; button.style.top = `${position.y}px`;
        colorize(button, task.status);
        button.setAttribute("aria-label", `${task.id}, ${task.title}, ${labels[task.status]}`);
        button.title = `${task.id} · ${task.title} · ${labels[task.status]}`;
        button.append(element("span", task.id, "node-id"), element("span", task.title, "node-title"), element("span", `${labels[task.status]} · ${scopes[task.scope]}`, "node-status"));
        motionClasses(button, task.id);
        button.addEventListener("click", () => select(task.id));
        button.addEventListener("focus", () => {if (document.activeElement.matches(":focus-visible")) center(task.id);});
        $("nodes").append(button);
      });
    });
    bounds = {width: Math.max(240, levels.length * 270 - 26), height: rows * 134 + 50};
    const svg = $("connections"), ns = "http://www.w3.org/2000/svg";
    svg.setAttribute("width", bounds.width); svg.setAttribute("height", bounds.height);
    const defs = document.createElementNS(ns, "defs");
    data.states.forEach((status) => {
      const marker = document.createElementNS(ns, "marker");
      Object.entries({id: `arrow-${status}`, viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse"}).forEach(([name, value]) => marker.setAttribute(name, value));
      const arrow = document.createElementNS(ns, "path"); arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z"); arrow.setAttribute("fill", colors[status]); marker.append(arrow); defs.append(marker);
    });
    svg.append(defs);
    let drawn = 0, hidden = 0;
    data.edges.forEach((edge) => {
      const from = positions.get(edge.from), to = positions.get(edge.to);
      if (!from || !to) {if (from || to) hidden++; return;}
      const path = document.createElementNS(ns, "path");
      const startX = from.x + 198, startY = from.y + 53, endX = to.x - 5, endY = to.y + 53;
      const control = Math.max(30, (endX - startX) / 2);
      path.setAttribute("d", `M${startX},${startY} C${startX + control},${startY} ${endX - control},${endY} ${endX},${endY}`);
      const status = tasks.get(edge.to).status;
      colorize(path, status);
      path.setAttribute("class", "edge"); path.setAttribute("marker-end", `url(#arrow-${status})`);
      path.dataset.from = edge.from; path.dataset.to = edge.to;
      svg.append(path); drawn++;
    });
    $("graph-count").textContent = `${visible.length} tareas · ${drawn} conexiones${hidden ? ` · ${hidden} fuera del filtro` : ""}${chain ? ` · Cadena de ${chain}` : ""}`;
    $("empty").hidden = visible.length > 0;
  }
  function relationSection(title, ids) {
    const section = element("section"); section.append(element("h3", `${title} (${ids.length})`));
    const list = element("div", undefined, "relation-list");
    ids.forEach((id) => {
      const task = tasks.get(id), button = element("button", id);
      colorize(button, task.status);
      button.title = `${task.title} · ${labels[task.status]}`;
      button.setAttribute("aria-label", `${id}, ${task.title}, ${labels[task.status]}`);
      button.addEventListener("click", () => select(id, false, true)); list.append(button);
    });
    if (!ids.length) list.append(element("p", "Sin tareas con ID explícito."));
    section.append(list); return section;
  }
  function imageGallery(images) {
    imageIndex = Math.min(imageIndex, images.length - 1);
    const gallery = element("div"), button = element("button", undefined, "evidence-image"), thumbnail = element("img"), caption = element("span"), counter = element("output");
    thumbnail.alt = "";
    button.append(thumbnail, caption);
    button.addEventListener("click", () => $("image-viewer").showModal());
    // Actualiza en el lugar: renderDetail perdería el foco y el scroll del panel.
    const show = () => {
      const image = images[imageIndex];
      button.setAttribute("aria-label", `Ampliar imagen: ${image.alt}`);
      thumbnail.src = image.src; caption.textContent = image.alt;
      counter.textContent = $("image-count").textContent = `${imageIndex + 1} / ${images.length}`;
      $("image-title").textContent = image.alt;
      $("image-full").src = image.src; $("image-full").alt = image.alt;
      $("image-full").parentElement.scrollTop = 0;
    };
    stepImage = (delta) => {imageIndex = (imageIndex + delta + images.length) % images.length; show(); slide(thumbnail, delta); slide($("image-full"), delta);};
    const stepper = (text, label, delta) => {
      const step = element("button", text);
      step.setAttribute("aria-label", label);
      step.addEventListener("click", () => stepImage(delta));
      return step;
    };
    show();
    $("image-nav").hidden = images.length < 2;
    gallery.append(button);
    if (images.length > 1) {
      const nav = element("div", undefined, "evidence-nav");
      nav.append(stepper("‹", "Imagen anterior", -1), counter, stepper("›", "Imagen siguiente", 1));
      gallery.append(nav);
    }
    return gallery;
  }
  function renderDetail() {
    document.querySelector(".workspace").classList.toggle("has-detail", Boolean(selected));
    const newTask = selected !== detailTask; detailTask = selected;
    if (!selected) {
      $("detail").replaceChildren();
      const placeholder = element("div", undefined, "detail-placeholder");
      placeholder.append(element("span", "EXPLORAR EL PLAN", "eyebrow"), element("h2", "Elegí una tarea"), element("p", "Consultá sus requisitos, las tareas que dependen de ella y sus criterios de aceptación."), element("p", "Usá la lista para centrar una tarea en el árbol."));
      $("detail").append(placeholder); return;
    }
    const task = tasks.get(selected), header = element("div", undefined, "detail-header"), body = element("div", undefined, "detail-body");
    body.classList.toggle("enter", newTask);
    const close = element("button", "Cerrar"); close.setAttribute("aria-label", "Cerrar detalle de tarea"); close.addEventListener("click", closeDetail);
    header.append(element("strong", task.id), close);
    const badge = element("span", undefined, "badge"); colorize(badge, task.status); badge.append(dot(task.status), element("span", `${labels[task.status]} · ${scopes[task.scope]}`));
    body.append(badge, element("h2", task.title));
    const module = data.modules.find((item) => item.id === task.module); body.append(element("p", module.title));
    if (chain || !visible.some((item) => item.id === task.id)) body.append(element("p", chain ? `Cadena completa de ${chain}; los filtros quedan suspendidos hasta salir.` : "Esta tarea quedó fuera de los filtros actuales."));
    const actions = element("div", undefined, "detail-actions"), branch = element("button", chain ? "Salir de la cadena" : "Ver cadena completa");
    branch.addEventListener("click", () => {chain = chain ? null : task.id; render();}); actions.append(branch);
    const edit = element("button", "Editar tarea"), instruct = element("button", "Dar instrucción a Codex"), copy = element("button", "Copiar contexto");
    edit.addEventListener("click", () => openEditor(task.id)); instruct.addEventListener("click", () => openInstruction(task.id));
    copy.addEventListener("click", () => copyText(promptFor(task.id)));
    actions.append(edit, instruct, copy, codexLink(task.id)); body.append(actions);
    if (task.images?.length) body.append(element("h3", "Evidencia visual"), imageGallery(task.images));
    body.append(relationSection("Requisitos", task.dependencies), relationSection("Dependientes", dependents.get(task.id)));
    for (const label of data.fieldNames) {
      body.append(element("h3", label === "Dependencias" ? "Dependencias: texto del plan" : fieldLabel(label)), element("p", task.fields[label]));
      if (label === "Capa") body.append(element("p", scopeDescriptions[task.scope]));
    }
    body.append(element("h3", "Especificación fuente"));
    const source = element("a", `${task.source} · línea ${task.line}`); source.href = task.sourceUrl; source.target = "_blank"; source.rel = "noopener"; body.append(source);
    $("detail").replaceChildren(header, body); $("detail").scrollTop = 0;
  }
  function closeDetail() {
    const previous = selected; selected = null;
    if (chain) {chain = null; render();} else {paintSelection(); renderDetail();}
    const listButton = [...document.querySelectorAll(".list-task")].find((button) => button.dataset.task === previous);
    (listButton || $("search")).focus({preventScroll: true});
  }
  function render(reframe = true) {
    const query = normalize($("search").value.trim()), module = $("module").value, scope = $("scope").value;
    const branch = chain ? chainIds(chain) : null;
    // render reconstruye los nodos: solo se anima lo que recién aparece, no todo en cada filtro o actualización.
    const previous = new Set(visible.map((task) => task.id));
    visible = data.tasks.filter((task) => branch ? branch.has(task.id) : states.has(task.status) && (!module || task.module === module) && (!scope || task.scope === scope) && (!query || normalize(`${task.id} ${task.title}`).includes(query)));
    entering = new Set(visible.filter((task) => !previous.has(task.id)).map((task) => task.id));
    document.querySelectorAll("[data-status]").forEach((button) => button.setAttribute("aria-pressed", String(states.has(button.dataset.status))));
    $("result-count").textContent = `${visible.length} / ${data.tasks.length}`;
    $("task-list").replaceChildren();
    visible.forEach((task) => {
      const button = element("button", undefined, "list-task"); button.dataset.task = task.id; colorize(button, task.status); motionClasses(button, task.id);
      const meta = element("span", undefined, "list-meta"); meta.append(dot(task.status), element("span", task.id), element("span", labels[task.status], "list-status"));
      button.append(meta, element("span", task.title, "list-title")); button.addEventListener("click", () => select(task.id, true)); $("task-list").append(button);
    });
    if (!visible.length) $("task-list").append(element("p", "No hay coincidencias. Restablecé los filtros para volver al plan completo.", "no-results"));
    drawGraph(); paintSelection(); renderDetail(); if (reframe) readableFrame();
  }
  $("filters").addEventListener("submit", (event) => event.preventDefault());
  for (const id of ["search", "module", "scope"]) $(id).addEventListener(id === "search" ? "input" : "change", () => {chain = null; render();});
  $("reset").addEventListener("click", () => {resetFilters(); selected = null; render(); $("search").focus();});
  $("zoom-in").addEventListener("click", () => zoom(1.3)); $("zoom-out").addEventListener("click", () => zoom(1 / 1.3)); $("fit").addEventListener("click", () => fit(true));
  viewport.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button") || event.button !== 0) return;
    drag = {id: event.pointerId, x: event.clientX, y: event.clientY, pan: {...pan}};
    viewport.setPointerCapture(event.pointerId); viewport.classList.add("dragging"); viewport.focus({preventScroll: true});
  });
  viewport.addEventListener("pointermove", (event) => {if (drag && drag.id === event.pointerId) {pan = {x: drag.pan.x + event.clientX - drag.x, y: drag.pan.y + event.clientY - drag.y}; transform();}});
  const endDrag = () => {drag = null; viewport.classList.remove("dragging");};
  viewport.addEventListener("pointerup", endDrag); viewport.addEventListener("pointercancel", endDrag); viewport.addEventListener("lostpointercapture", endDrag);
  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    if (event.ctrlKey || event.metaKey) {const rect = viewport.getBoundingClientRect(); zoom(Math.exp(-event.deltaY * .006), event.clientX - rect.left, event.clientY - rect.top);}
    else {pan.x -= event.deltaX; pan.y -= event.deltaY; transform();}
  }, {passive: false});
  viewport.addEventListener("keydown", (event) => {
    if (event.target !== viewport) return;
    const deltas = {ArrowLeft: [60, 0], ArrowRight: [-60, 0], ArrowUp: [0, 60], ArrowDown: [0, -60]};
    if (deltas[event.key]) {event.preventDefault(); pan.x += deltas[event.key][0]; pan.y += deltas[event.key][1]; transform();}
    if (["+", "=", "-"].includes(event.key)) {event.preventDefault(); zoom(event.key === "-" ? 1 / 1.3 : 1.3);}
    if (event.key === "Home") {event.preventDefault(); fit(true);}
  });
  $("help-open").addEventListener("click", () => $("help").showModal());
  const closeHelp = () => {$("help").close(); $("help-open").focus();};
  $("help-close").addEventListener("click", closeHelp); $("help-done").addEventListener("click", closeHelp);
  $("help").addEventListener("cancel", (event) => {event.preventDefault(); closeHelp();});
  $("image-close").addEventListener("click", () => $("image-viewer").close());
  $("image-prev").addEventListener("click", () => stepImage(-1)); $("image-next").addEventListener("click", () => stepImage(1));
  $("image-viewer").addEventListener("keydown", (event) => {
    const delta = {ArrowLeft: -1, ArrowRight: 1}[event.key];
    if (delta && !$("image-nav").hidden) {event.preventDefault(); stepImage(delta);}
  });
  document.addEventListener("keydown", (event) => {if (event.key === "Escape" && !document.querySelector("dialog[open]") && selected) {event.preventDefault(); closeDetail();}});
  new ResizeObserver(() => selected && positions.has(selected) ? center(selected) : readableFrame()).observe(viewport);
  render();

  function liveStatus(mode, text, error = "") {
    const badge = $("live-status");
    badge.dataset.mode = mode;
    if (badge.textContent !== text) badge.textContent = text;
    badge.title = error;
    $("live-error").hidden = !error;
    $("live-error").textContent = error;
  }
  function applyUpdate(next) {
    const previous = {pan: {...pan}, scale, detailScroll: $("detail").scrollTop};
    const focused = document.activeElement;
    const focusedTask = focused?.dataset.task;
    const focusedClass = focused?.classList.contains("list-task") ? ".list-task" : ".node";
    const previousStatus = new Map(data.tasks.map((task) => [task.id, task.status]));
    data = next;
    changed = new Set(data.tasks.filter((task) => previousStatus.has(task.id) && previousStatus.get(task.id) !== task.status).map((task) => task.id));
    document.title = `Árbol de tareas · ${data.projectName}`;
    $("project-name").textContent = data.projectName;
    tasks.clear(); dependents.clear(); fullLevels.clear();
    data.tasks.forEach((task) => {tasks.set(task.id, task); dependents.set(task.id, []);});
    data.edges.forEach((edge) => dependents.get(edge.from).push(edge.to));
    data.tasks.forEach((task) => level(task.id));
    if (selected && !tasks.has(selected)) selected = null;
    if (chain && !tasks.has(chain)) chain = null;
    const currentModule = $("module").value;
    $("module").replaceChildren(element("option", "Todos los módulos"));
    $("module").firstChild.value = "";
    data.modules.forEach((module) => {const option = element("option", module.title); option.value = module.id; $("module").append(option);});
    $("module").value = data.modules.some((module) => module.id === currentModule) ? currentModule : "";
    document.querySelectorAll(".state-card").forEach((button) => {
      const count = data.tasks.filter((task) => task.status === button.dataset.status).length;
      button.querySelector(".count").textContent = count;
      button.setAttribute("aria-label", `${labels[button.dataset.status]}: ${count} tareas`);
    });
    render(false);
    changed = new Set();
    $("detail").scrollTop = previous.detailScroll;
    if (focusedTask) {
      const replacement = [...document.querySelectorAll(focusedClass)].find((node) => node.dataset.task === focusedTask);
      (replacement || $("search")).focus({preventScroll: true});
    }
    scale = previous.scale; pan = previous.pan; transform();
    document.querySelector(".snapshot time").textContent = data.generatedAt;
    $("roadmap-data").textContent = JSON.stringify(data);
  }
  if (data.live && ["http:", "https:"].includes(location.protocol)) {
    liveStatus("connecting", "Conectando actualización automática…");
    const request = async (url) => {
      const response = await fetch(url, {cache: "no-store", signal: AbortSignal.timeout(3000)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    };
    async function poll() {
      try {
        const status = await request(data.live.statusUrl);
        if (status.status === "invalid") liveStatus("invalid", "Cambios inválidos · última versión válida", status.error);
        else {
          if (status.revision !== data.revision) applyUpdate(await request(data.live.dataUrl));
          liveStatus("connected", "Actualización automática activa");
        }
      } catch {
        liveStatus("disconnected", "Sin conexión · reintentando");
      } finally {setTimeout(poll, data.live.intervalMs);}
    }
    poll();
    document.addEventListener("visibilitychange", () => {if (!document.hidden) $("live-status").textContent = "Comprobando cambios…";});
  } else liveStatus("static", "Copia local · sin sincronización");
})();
