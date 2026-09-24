# Material — PR `feat(umbriel): add noctalia Umbriel compositor support`

Material consolidado para uso como título/corpo da PR a ser aberta em
`https://github.com/nwg-piotr/nwg-displays`. Use o trecho marcado em
`<PR_BODY>` ao abrir a PR.

## Contexto

`nwg-displays` é um GUI GTK para configuração de monitores escrito em
Python. Historicamente suporta três compositors Wayland: sway (via
i3-IPC), Hyprland (via socket próprio) e Niri (via niri IPC).

O usuário roda **[Umbriel](https://github.com/noctalia-dev/umbriel)** (o
compositor do projeto noctalia), que não fala nenhum desses protocolos.
Até hoje, quem queria organizar saídas no umbriel tinha que editar
`~/.config/umbriel/config.toml` à mão — não existia ferramenta
interativa.

## Solução

Adicionar um adapter que:

1. detecta umbriel via `UMBRIEL_SOCKET` ou
   `$XDG_RUNTIME_DIR/umbriel-$WAYLAND_DISPLAY.sock`;
2. lê outputs com `umbriel outputs --json` (wlr-output-management v1);
3. gera um arquivo TOML `outputs.toml` no formato do umbriel;
4. injeta `outputs.toml` no `[include] files` do `config.toml`
   idempotentemente;
5. deixa o hot-reload de arquivo do umbriel aplicar (sem IPC reload);
6. usa `umbriel msg dpms-on:NAME` para ligar/desligar um output por vez
   na hora.

Formato de saída (`outputs.toml`):

```toml
[output."DP-1"]
mode = "3840x2160@165.000"
position = [0, 0]
scale = 1.0
vrr = "fullscreen"

[output."HDMI-A-1"]
enabled = false
```

## Mudanças

| arquivo | linhas | descrição |
|---|---|---|
| `nwg_displays/umbriel.py` | +267 (novo) | detector + TOML serializer + include injector |
| `nwg_displays/tools.py` | +15 / -2 | `umbriel` branch em `list_outputs` / `list_outputs_activity` |
| `nwg_displays/main.py` | +52 / -2 | detecção, `--monitors_path`, Gdk fetch, workspaces disabled |
| `nwg_displays/settings_applier/settings_applier.py` | +96 | `_apply_umbriel_json` + `_apply_umbriel_gui` |
| `tests/test_umbriel_adapter.py` | +354 (novo) | 20 testes unitários |
| `README.md` | +30 | seção "Umbriel" + lista de compositors |

Total: **+807 / -6** linhas em 6 arquivos.

## Como foi construído (ordem cronológica)

1. pesquisa sobre umbriel — docs + fonte `src/cli/outputs.cpp` para
   entender o JSON real de `umbriel outputs --json` (não documentado
   oficialmente);
2. estudo dos adapters sway/hyprland/niri já presentes em `tools.py`
   e `settings_applier.py`, com cópia leve de padrão do Niri (que é o
   que mais se parece em formato "config + hot reload" + IPC opcional);
3. escrita de `umbriel.py` (zero dependência nova, só stdlib);
4. ramificações cirúrgicas em `tools.py`, `main.py`,
   `settings_applier.py` — cada diff menor que 100 linhas;
5. testes unitários cobrindo: detecção, parser do JSON, serializer
   TOML, injetor de include (criar/apendar/sobrescrever/ser
   idempotente), round-trip via `tomllib`;
6. validação local: `pipx install --editable
   --python /usr/bin/python3 --system-site-packages <repo>` dentro de
   sessão umbriel real; `nwg-displays` abriu GUI,
   detectou display Lenovo 0x9051, mostrou 9 modos. Screenshot
   capturado via `grim` confirma funcionamento ponta-a-ponta.

## Testes inclusos

20 testes (`python3 tests/test_umbriel_adapter.py`), zero dependência
extra:

- `TestToDisplaysDict`: parsing do JSON umbriel → dict interno
- `TestSaveOutputs`: serialização TOML em 5 modos (ativo, desativado,
  com rotação, com descrição /use-desc, com caracteres escapados)
- `TestEnsureInclude`: 5 cenários do injetor de `[include]` (criar,
  anexar, idempotente, já com `files=`, `[include]` sem `files`)
- `TestEndToEnd`: 5 cenários de round-trip `tomllib.load()` + `save`
  (arquivos gerados re-parseiam idênticos)
- `TestIsUmbriel`: detecção por env vs socket inexistente

Resultado: **20/20 OK**.

## Verificação manual realizada (sessão umbriel real)

- `nwg-displays -h` mostrou default
  `--monitors_path /home/pponto/.config/umbriel/outputs.toml`
- `nwg-displays -v` retornou `nwg-displays version 0.4.4` sem
  AttributeError no `args.num_ws`
- GUI abriu dentro do noctalia em cima da layer-shell; display
  `eDP-1` identificado como `Lenovo Group Limited 0x9051`,
  1920×1080@60Hz, scale 1.0, 9 modos listados
- Janela GtkLayerShell.Em compositor hot-reload já prepararia
  `outputs.toml` ao clicar Apply (teste manual não realizado; ver
  "Limitações conhecidas")

## Limitações conhecidas (escopo intencional)

- **Sem workspace assignment GUI**: umbriel usa
  `workspaces = N` (ou lista nomeada) por `[output.*]`. Em vez de
  criar UI nova, o botão "Workspaces" fica desativado com tooltip
  apontando para edição manual de `outputs.toml`. Mirror do que já é
  feito para Niri.
- **HDR não emitido**: `hdr = "auto"` poderia ser adicionado, mas o
  caminho de descoberta exige UI nova (toggle similar ao `cm` do
  Hyprland). Fora do escopo inicial.
- **`sdr_brightness` / `sdr_saturation` não emitidos**: features
  Hyprland-only; sem equivalente umbriel.
- **`focused` sem valor real**: `umbriel outputs --json` não devolve
  qual display está focado; flag fica `False` na primeira leitura. Niri
  tem o mesmo comportamento.
- **`tearing`, `direct_scanout`**: campos suportados pelo umbriel mas
  sem UI no nwg-displays original (Hyprland também não emite).
  Adicionar exigiria UI nova.
- **Reconfiguração direta via wlr-output-management**: alternativa
  não tomada — manter consistência com o caminho "config file +
  hot-reload" simplifica leitura de estado.
- **DPMS via `umbriel msg`**: só usado dentro do GUI (toggle on/off)
  porque TOML só consegue expressar `enabled`.

## Compatibilidade

- Python ≥ 3.11 (uso de `tomllib` via stdlib nos testes; runtime
  usaria Python ≥ 3.6 como o setup.py original exige)
- Dependências: nenhuma nova. Reusa `python-gobject`, `gtk3`,
  `gtk-layer-shell` já exigidas pelo nwg-displays
- `umbriel` CLI deve estar no `PATH` para `umbriel outputs --json`
  funcionar; tipicamente instalado em `/usr/bin/umbriel`

## Créditos

A contribuição foi preparada com assistência do assistente IA
**MiniMax-M3 (opencode-go/minimax-m3)** operando no opencode,
com o usuário `pponto` (Codeberg) dirigindo cada decisão de
escopo, validando em sessão real, e autorizando mudanças.

Comandos, testes e validação GUI foram executados pelo usuário no
computador dele — não em ambiente isolado. Toda decisão de
arquitetura (escolha de TOML vs wlr-output-management, escolha de
Niri como referência, escolha de manter workspace dialog fora do
escopo) foi tomada em conjunto.

---

<PR_BODY>

## Summary

Add first-class support for [Umbriel](https://github.com/noctalia-dev/umbriel)
(noctalia) Wayland compositor to `nwg-displays`.

Umbriel uses TOML configuration with file-watcher hot-reload and
does not implement i3-IPC, Hyprland IPC, or Niri IPC. This adapter
writes `[output."NAME"] { mode, position, scale, vrr, enabled }`
to an included file, leaving Umbriel's file watcher to apply on
save. DPMS is toggled live via `umbriel msg dpms-on:NAME`.

## What's in this PR

- New module `nwg_displays/umbriel.py`: detection
  (`UMBRIEL_SOCKET` env var or
  `$XDG_RUNTIME_DIR/umbriel-$WAYLAND_DISPLAY.sock`),
  `umbriel outputs --json` parser, TOML serializer, idempotent
  `[include] files` injector
- `tools.py`: umbriel branches in `list_outputs()` and
  `list_outputs_activity()`
- `main.py`: detection at top level + `--monitors_path` defaults to
  `~/.config/umbriel/outputs.toml`; workspaces dialog disabled
  (Umbriel uses `workspaces = N` per output)
- `settings_applier.py`: `_apply_umbriel_json` + `_apply_umbriel_gui`
- `tests/test_umbriel_adapter.py`: 20 unit tests, all green
- `README.md`: Umbriel section

## Test plan

1. `pipx install --editable --python /usr/bin/python3
   --system-site-packages <repo>` (depends on system gtk bindings)
2. Inside an Umbriel session, run `nwg-displays`
3. App detects display, lets you reorder / rescale / toggle DPMS
4. Click Apply → `~/.config/umbriel/outputs.toml` updated,
   `config.toml` patched with `[include] files = [..., "outputs.toml"]`
5. Umbriel reloads automatically; new layout applied

## Credits

Authored by @pponto-source with assistance from the
`MiniMax-M3 (opencode-go/minimax-m3)` AI coding assistant. All
decisions and manual validation were performed by the human author;
the assistant handled implementation, research on Umbriel's CLI JSON
schema (read from `noctalia-dev/umbriel/src/cli/outputs.cpp`),
and writing of test cases.

</PR_BODY>
