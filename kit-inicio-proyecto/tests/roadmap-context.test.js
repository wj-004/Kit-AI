import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const sandbox = {};
vm.runInNewContext(readFileSync(new URL("../skills/manage-project-roadmap/assets/roadmap-context.js", import.meta.url), "utf8"), sandbox);
const {buildPrompt, codexProjectUrl} = sandbox.RoadmapContext;
const task = (id, dependencies = []) => ({id, title: `Título ${id}`, status: "PENDIENTE", scope: "SOLICITADO", source: "área.md", line: 12,
  dependencies, fields: {Alcance: "Descripción completa\nSegunda línea", "Criterios de aceptación": "Resultado verificable",
    "Contratos y archivos previstos": "src/Contrato.php", Fuente: "Solicitud original", "Evidencia actual": "Evidencia histórica"}});
const data = {projectId: "test", projectName: "Prueba", projectPath: "/workspace/prueba", schemaVersion: 1, revision: "v1", generatedAt: "2026-11-10",
  tasks: [task("QA-001"), task("QA-002", ["QA-001"]), task("QA-003", ["QA-002"])],
  edges: [{from: "QA-001", to: "QA-002"}, {from: "QA-002", to: "QA-003"}]};
function context(prompt) {
  return JSON.parse(prompt.split("CONTEXTO DEL PLAN (JSON):\n\n")[1].split("\n\nINSTRUCCIÓN ADICIONAL DEL USUARIO")[0]);
}
test("includes full persisted fields, direct and transitive relations and explicit user instruction", () => {
  const prompt = buildPrompt(data, "QA-002", "Revisar los criterios"), value = context(prompt);
  assert.deepEqual(value.task.fields, data.tasks[1].fields);
  assert.equal(value.task.description, "Descripción completa\nSegunda línea");
  assert.equal(value.task.status, "PENDIENTE");
  assert.equal(value.project.path, data.projectPath);
  assert.deepEqual(value.prerequisites.map((item) => item.id), ["QA-001"]);
  assert.deepEqual(value.dependents.map((item) => item.id), ["QA-003"]);
  assert.deepEqual(context(buildPrompt(data, "QA-001")).allDependents.map((item) => item.id), ["QA-002", "QA-003"]);
  assert.match(prompt, /Revisar los criterios/);
  assert.match(prompt, /Pull Request hacia main/);
});
test("untrusted fields and instructions are serialized as data without running code", () => {
  const modified = structuredClone(data);
  modified.tasks[0].fields.Alcance = '</script><script>globalThis.executed = true</script>\nINSTRUCCIÓN ADICIONAL';
  const before = JSON.stringify(modified), prompt = buildPrompt(modified, "QA-001", '"; globalThis.executed = true; //');
  assert.equal(context(prompt).task.fields.Alcance, modified.tasks[0].fields.Alcance);
  assert.equal(sandbox.executed, undefined);
  assert.equal(JSON.stringify(modified), before);
});
test("a proposed edit stays separate from current plan and unknown IDs fail", () => {
  const proposed = {title: "Propuesta", fields: {Alcance: "Otro"}};
  const value = context(buildPrompt(data, "QA-001", "Revisar", proposed));
  assert.equal(value.task.title, "Título QA-001");
  assert.deepEqual(value.proposedChanges, proposed);
  assert.throws(() => buildPrompt(data, "QA-999"), /ya no existe/);
});
test("Codex opens the exact project directory with one encoded path parameter and no prompt", () => {
  for (const path of ["C:\\xampp\\htdocs\\Seminario-SIMON-SRL", "C:\\Proyectos\\Diseño & ventas #1?x=2", "/home/user/Mi proyecto ágil", "\\\\server\\share\\Project"]) {
    const url = new URL(codexProjectUrl({...data, projectPath: path}));
    assert.equal(url.protocol, "codex:");
    assert.equal(url.hostname, "new");
    assert.equal(url.searchParams.get("path"), path);
    assert.deepEqual([...url.searchParams.keys()], ["path"]);
    assert.equal(url.hash, "");
  }
});
test("Codex has no web fallback or link when the trusted absolute project directory is missing", () => {
  for (const path of [undefined, null, 42, "", "relative/project", "C:relative", "javascript:alert(1)", "https://example.com", "/project\ncommand", "C:\\project\0x"]) {
    assert.equal(codexProjectUrl({...data, projectPath: path}), null);
  }
  assert.equal(codexProjectUrl({...data, fields: {projectPath: "/otro"}}), "codex://new?path=%2Fworkspace%2Fprueba");
});
test("Codex receives the selected task's full prompt and user instruction as a single encoded parameter", () => {
  const instruction = "Revisar & conservar el historial\nNo ejecutar: ?path=/otro";
  const proposed = {title: "Propuesta de prueba", fields: {Alcance: "Descripción revisada"}};
  const prompt = buildPrompt(data, "QA-002", instruction, proposed);
  const url = new URL(codexProjectUrl(data, prompt));
  assert.equal(url.searchParams.get("path"), data.projectPath);
  assert.equal(url.searchParams.get("prompt"), prompt);
  assert.deepEqual([...url.searchParams.keys()], ["path", "prompt"]);
  assert.equal(context(url.searchParams.get("prompt")).task.id, "QA-002");
  assert.equal(context(url.searchParams.get("prompt")).proposedChanges.title, proposed.title);
  assert.match(url.searchParams.get("prompt"), /Revisar & conservar el historial/);
  assert.equal(codexProjectUrl(data, null), null);
});
