// Run: node --test tests/tab-navigation.test.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "../ui/index.html"), "utf8");
const commands = JSON.parse(html.match(/const COMMANDS = (\[[\s\S]*?\]);/)[1]);
const match = html.match(/\$\("cmd"\)\.addEventListener\("keydown", e => \{[\s\S]*?\n\}\);/);
assert.ok(match, "terminal keydown handler exists");
const cases = [
  ["empty input", "", {}, "", false],
  ["complete command", "help", {}, "help", false],
  ["partial command", "h", {}, "help", true],
  ["case-insensitive partial", "HE", {}, "help", true],
  ["unmatched command", "unmatched", {}, "unmatched", false],
  ...["shiftKey", "ctrlKey", "altKey", "metaKey", "isComposing"]
    .map(key => [key, "h", {[key]: true}, "h", false]),
];
for (const [name, value, flags, wantValue, wantPrevent] of cases) {
  test(name, () => {
    let handler;
    const context = vm.createContext({
      COMMANDS: commands,
      $: () => ({addEventListener: (_, fn) => { handler = fn; }}),
    });
    vm.runInContext(match[0], context, {timeout: 100});
    const target = {value};
    let prevented = false;
    handler({key:"Tab", target, ...flags, preventDefault(){prevented = true;}});
    assert.equal(target.value, wantValue);
    assert.equal(prevented, wantPrevent);
  });
}
test("viewport does not disable zoom", () => {
  const viewport = html.match(/<meta name="viewport"[^>]*>/)[0];
  assert.doesNotMatch(viewport, /user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:\D|$)/i);
});
