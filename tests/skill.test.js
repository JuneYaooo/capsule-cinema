// tests/skill.test.js — Capsule Cinema OpenClaw Skill 基础测试
import assert from 'assert';
import { relative, resolve, join, dirname } from 'path';
import { existsSync, readFileSync, readdirSync, lstatSync, mkdirSync, mkdtempSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, '..');

function listTextFiles(dir) {
  try {
    return execFileSync('git', ['ls-files'], { cwd: dir, encoding: 'utf-8' })
      .split('\n')
      .map(line => line.trim())
      .filter(name => /\.(py|js|json|md|yaml|yml)$/.test(name))
      .map(name => join(dir, name))
      .filter(file => existsSync(file));
  } catch {
    const entries = readdirSync(dir, { withFileTypes: true });
    const files = [];
    const skippedDirs = new Set([
      '.git', '.venv', 'node_modules', '__pycache__',
      '.pytest_cache', '.worktrees', 'output', 'artifacts',
      'analysis_outputs', 'reports',
    ]);
    for (const entry of entries) {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (skippedDirs.has(entry.name)) continue;
        files.push(...listTextFiles(fullPath));
      } else if (/\.(py|js|json|md|yaml|yml)$/.test(entry.name)) {
        files.push(fullPath);
      }
    }
    return files;
  }
}

function sorted(values) {
  return [...values].sort();
}

function extractSkillEnvs() {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const envSection = skillContent.match(/  env:\n([\s\S]*?)\n\ninputs:/);
  assert.ok(envSection, 'skill.md 应包含 env 列表');
  return envSection[1]
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('- ') && !line.startsWith('- #'))
    .map(line => line.replace('- ', ''));
}

function extractIndexAllowedEnvs() {
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const allowlist = jsContent.match(/const ALLOWED_ENV_KEYS = \[([\s\S]*?)\];/);
  assert.ok(allowlist, 'index.js 应包含 ALLOWED_ENV_KEYS');
  return [...allowlist[1].matchAll(/'([^']+)'/g)].map(match => match[1]);
}

function extractEnvExampleKeys() {
  const content = readFileSync(join(SKILL_DIR, 'lib', '.env.example'), 'utf-8');
  return content
    .split('\n')
    .map(line => line.match(/^\s*([A-Z][A-Z0-9_]*)=/)?.[1])
    .filter(Boolean);
}

function loadEnvRegistry() {
  const registry = JSON.parse(readFileSync(join(SKILL_DIR, 'lib', 'config', 'env_registry.json'), 'utf-8'));
  assert.ok(Array.isArray(registry.env), 'env_registry.json 应包含 env 数组');
  return registry.env;
}

function loadToolRegistryNames() {
  const content = readFileSync(join(SKILL_DIR, 'lib', 'config', 'tool_registry.yaml'), 'utf-8');
  const names = [];
  for (const match of content.matchAll(/^  ([A-Za-z][A-Za-z0-9_]*):\s*$/gm)) {
    names.push(match[1]);
  }
  assert.ok(names.length >= 10, 'tool_registry.yaml 应声明可调用工具');
  return new Set(names);
}

function loadCapsulePackageManifest(name) {
  const capsuleDir = join(SKILL_DIR, 'capsules', `${name}.capsule`);
  assert.ok(existsSync(capsuleDir), `${name}.capsule 应存在`);
  const python = process.env.PYTHON_BIN || 'python3.12';
  const raw = execFileSync(
    python,
    [
      '-c',
      'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=False))',
      join(capsuleDir, 'capsule.yaml'),
    ],
    { encoding: 'utf-8' }
  );
  return { capsule: JSON.parse(raw) };
}

function listCapsulePackageEntries(name) {
  const capsuleDir = join(SKILL_DIR, 'capsules', `${name}.capsule`);
  assert.ok(existsSync(capsuleDir), `${name}.capsule 应存在`);
  const entries = [];
  const visit = (dir, prefix = '') => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        visit(full, rel);
      } else {
        entries.push(rel);
      }
    }
  };
  visit(capsuleDir);
  return entries.sort();
}

function listPackagedCapsuleNames() {
  return readdirSync(join(SKILL_DIR, 'capsules'))
    .filter(name => name.endsWith('.capsule'))
    .map(name => name.replace(/\.capsule$/, ''))
    .sort();
}

function assertSkillDeclaresIo(name, section) {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const nextSection = section === 'inputs' ? 'outputs:' : 'tags:';
  const pattern = new RegExp(`${section}:\\n([\\s\\S]*?)\\n${nextSection}`);
  const match = skillContent.match(pattern);
  assert.ok(match, `skill.md 应包含 ${section} 列表`);
  assert.ok(match[1].includes(`name: ${name}`), `skill.md ${section} 应声明 ${name}`);
}

// 测试 1: skill.md 存在且包含必要的 YAML 前置字段
function testSkillMdExists() {
  const skillPath = join(SKILL_DIR, 'skill.md');
  assert.ok(existsSync(skillPath), 'skill.md 文件应存在');

  const content = readFileSync(skillPath, 'utf-8');

  // 验证 YAML frontmatter 存在
  assert.ok(content.startsWith('---'), 'skill.md 应以 YAML frontmatter 开头');

  // 验证必要字段
  const requiredFields = [
    'name:', 'version:', 'description:', 'author:', 'license:',
    'capabilities:', 'permissions:', 'inputs:', 'outputs:',
    'tags:', 'minOpenClawVersion:',
  ];
  for (const field of requiredFields) {
    assert.ok(content.includes(field), `应包含 ${field} 字段`);
  }

  console.log('  ✅ skill.md 结构验证通过');
}

// 测试 2: index.js 导出 execute 函数（ES module）
async function testIndexJsExports() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  assert.ok(typeof mod.execute === 'function', 'index.js 应导出 execute 函数');
  console.log('  ✅ index.js 导出验证通过');
}

// 测试 3: package.json 格式正确
function testPackageJson() {
  const pkgPath = join(SKILL_DIR, 'package.json');
  assert.ok(existsSync(pkgPath), 'package.json 应存在');

  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
  assert.strictEqual(pkg.name, 'capsule-cinema', 'package name 应为 capsule-cinema');
  assert.strictEqual(pkg.version, '2.0.0', 'package version 应为 2.0.0');
  assert.ok(pkg.main === 'index.js', 'main 应为 index.js');
  assert.ok(pkg.type === 'module', 'type 应为 module');
  assert.ok(pkg.peerDependencies?.['@openclaw/skill-sdk'], '应声明 @openclaw/skill-sdk peerDependency');
  console.log('  ✅ package.json 验证通过');
}

// 测试 3a: OpenClaw 宿主 SDK 是运行时 peer，不应让 CI 从公共 npm 强制安装
function testOpenClawSdkPeerIsOptionalForCiInstall() {
  const pkg = JSON.parse(readFileSync(join(SKILL_DIR, 'package.json'), 'utf-8'));

  assert.ok(pkg.peerDependencies?.['@openclaw/skill-sdk'], '应保留 @openclaw/skill-sdk peerDependency');
  assert.strictEqual(
    pkg.peerDependenciesMeta?.['@openclaw/skill-sdk']?.optional,
    true,
    '@openclaw/skill-sdk 应标记为 optional peer，避免 npm install 在 CI 中拉取未公开宿主包'
  );

  console.log('  ✅ OpenClaw SDK optional peer 验证通过');
}

// 测试 3a: 测试资产必须可提交，CI 才能复现本地验证
function testTestsDirectoryIsVersionable() {
  const gitignore = readFileSync(join(SKILL_DIR, '.gitignore'), 'utf-8');
  assert.ok(!/^tests\/\s*$/m.test(gitignore), '.gitignore 不应整体忽略 tests/');
  assert.ok(existsSync(join(SKILL_DIR, 'tests', 'skill.test.js')), 'Node 测试入口应存在');
  assert.ok(existsSync(join(SKILL_DIR, 'tests', 'python', 'test_score_video_quality.py')), 'Python QA 回归测试应存在');
  const rootPythonTests = readdirSync(join(SKILL_DIR, 'tests'))
    .filter(name => /^test_.*\.py$/.test(name));
  assert.deepStrictEqual(
    rootPythonTests,
    [],
    '不要在 tests/ 根目录保留未被 npm test 覆盖且依赖 output/ 的 pytest；请移入 tests/python 或删除一次性产物测试'
  );
  console.log('  ✅ 测试资产入仓策略验证通过');
}

// 测试 3b: OpenClaw 元数据名称和版本对齐
function testMetadataAlignment() {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const pkg = JSON.parse(readFileSync(join(SKILL_DIR, 'package.json'), 'utf-8'));
  const openclaw = JSON.parse(readFileSync(join(SKILL_DIR, 'openclaw.plugin.json'), 'utf-8'));
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');

  assert.ok(skillContent.includes('name: capsule-cinema'), 'skill.md name 应为 capsule-cinema');
  assert.ok(skillContent.includes('version: 2.0.0'), 'skill.md version 应为 2.0.0');
  assert.strictEqual(pkg.name, 'capsule-cinema', 'package.json name 应为 capsule-cinema');
  assert.strictEqual(pkg.version, '2.0.0', 'package.json version 应为 2.0.0');
  assert.strictEqual(openclaw.id, 'capsule-cinema', 'openclaw.plugin.json id 应为 capsule-cinema');
  assert.strictEqual(openclaw.name, 'Capsule Cinema', 'openclaw.plugin.json name 应为 Capsule Cinema');
  assert.ok(jsContent.includes("id: 'capsule-cinema'"), 'index.js plugin id 应为 capsule-cinema');
  assert.ok(jsContent.includes("name: 'Capsule Cinema'"), 'index.js plugin name 应为 Capsule Cinema');

  console.log('  ✅ 元数据名称和版本对齐验证通过');
}

// 测试 4: 引用文件完整性
function testReferencesExist() {
  const refDir = join(SKILL_DIR, 'references');
  const expectedFiles = ['tools-api.md', 'engines-and-voices.md', 'video-recipes.md', 'storyboard-schema.md'];

  for (const file of expectedFiles) {
    assert.ok(existsSync(join(refDir, file)), `references/${file} 应存在`);
  }
  console.log('  ✅ 引用文件完整性验证通过');
}

// 测试 4b: 内置配置文件完整性
function testRuntimeConfigExists() {
  const configDir = join(SKILL_DIR, 'lib', 'config');
  const expectedFiles = ['doubao_voices.yaml', 'music_scenes.yaml', 'video_engines.yaml'];
  expectedFiles.push('env_registry.json');

  for (const file of expectedFiles) {
    assert.ok(existsSync(join(configDir, file)), `lib/config/${file} 应存在`);
  }
  const musicConfig = readFileSync(join(configDir, 'music_scenes.yaml'), 'utf-8');
  assert.ok(musicConfig.includes('online_music_styles:'), 'music_scenes.yaml 应声明在线音乐风格');
  assert.ok(!musicConfig.includes('music_library:'), 'music_scenes.yaml 不应声明本地音乐库');
  assert.ok(!/^\s*[^#\n]+\.mp3:/m.test(musicConfig), 'music_scenes.yaml 不应声明本地 mp3 音乐库条目');

  const readConfigTool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'utilities', 'read_config_yaml_tool.py'), 'utf-8');
  assert.ok(!readConfigTool.includes("get('music_library')"), '读取音乐配置时不应回退到本地 music_library');

  const musicUtils = readFileSync(join(SKILL_DIR, 'lib', 'src', 'utils', 'music_utils.py'), 'utf-8');
  assert.ok(!musicUtils.includes('VIDEO_RESOURCES_PATH'), '背景音乐选择不应扫描 VIDEO_RESOURCES_PATH 本地音乐库');
  assert.ok(!musicUtils.includes('/ "music"'), '背景音乐选择不应扫描 video_resources/music');

  const postProcessor = readFileSync(join(SKILL_DIR, 'lib', 'src', 'runtime', 'general_video_crew', 'post_processor.py'), 'utf-8');
  assert.ok(postProcessor.includes('bgm_output_path'), '后处理应显式生成 BGM 输出路径，避免覆盖输入视频');
  assert.ok(postProcessor.includes('output_path=str(bgm_output_path)'), '添加 BGM 时应传入独立 output_path');

  const runVideo = readFileSync(join(SKILL_DIR, 'scripts', 'run_video.py'), 'utf-8');
  assert.ok(runVideo.includes('def str2bool'), 'run_video.py 应显式解析布尔参数');
  assert.ok(!runVideo.includes('type=bool'), 'run_video.py 不应使用 argparse type=bool');
  assert.ok(runVideo.includes('--bgm_volume", type=float, default=None'), 'run_video.py 不应默认用 BGM 音量覆盖 AI 选择');

  const capsuleStore = readFileSync(join(SKILL_DIR, 'scripts', 'capsule_store.py'), 'utf-8');
  const capsuleRuntime = readFileSync(join(SKILL_DIR, 'scripts', 'capsule_runtime.py'), 'utf-8');
  const localCapsuleDocs = readFileSync(join(SKILL_DIR, 'references', 'local-capsule-sqlite.md'), 'utf-8');
  const gptImage2Tool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'image_generation', 'seedream5_image_generator_tool.py'), 'utf-8');
  const veo3Tool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'video_generation', 'veo3_video_generator_tool.py'), 'utf-8');
  const workspaceManager = readFileSync(join(SKILL_DIR, 'scripts', 'workspace_manager.py'), 'utf-8');
  const workflowConfig = readFileSync(join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'config.py'), 'utf-8');
  const removedScriptPackage = ['script', 'package'].join('_');
  const removedPitfallCommand = ['add', 'pitfall'].join('-');
  const removedSchemaTokens = [
    ['capsule', 'config', 'json'].join('_'),
    ['default', 'params', 'json'].join('_'),
    'row["mode"]',
  ];
  const removedAssetsSchemaToken = new RegExp(String.raw`(?<!local_)${['assets', 'json'].join('_')}`);
  assert.ok(!capsuleStore.includes(`choices=sorted(EXECUTION_MODES | {"${removedScriptPackage}"})`), 'capsule_store.py CLI 不应保留旧脚本包模式入口');
  assert.ok(!capsuleStore.includes(`${removedScriptPackage}_ref`), 'capsule_store.py 不应继续从旧脚本包 ref 恢复本地脚本');
  assert.ok(!capsuleStore.includes(`${removedScriptPackage}_key`), 'capsule_store.py 不应继续从旧脚本包 key 恢复本地脚本');
  assert.ok(!capsuleStore.includes(`"${removedScriptPackage}"`), 'capsule_store.py 不应继续接受旧脚本包作为本地资产 role');
  assert.ok(!capsuleStore.includes(removedPitfallCommand), 'capsule_store.py 不应保留旧 pitfall CLI 别名');
  for (const token of removedSchemaTokens) {
    assert.ok(!capsuleStore.includes(token), `capsule_store.py 不应读取旧 schema 字段: ${token}`);
  }
  assert.ok(!removedAssetsSchemaToken.test(capsuleStore), 'capsule_store.py 不应读取旧 assets_json schema');
  assert.ok(!capsuleRuntime.includes(['LEGACY', 'REPO', 'ROOT'].join('_')), 'capsule_runtime.py 不应保留旧仓库 DB 路径候选');
  assert.ok(!localCapsuleDocs.includes(`${removedScriptPackage}\` is accepted`), '本地胶囊文档不应继续公开旧脚本包模式');
  assert.ok(localCapsuleDocs.includes('capsules/<name>.capsule/'), '本地胶囊文档应声明 active 目录包路径');
  assert.ok(localCapsuleDocs.includes('archive/legacy_capsule_zips/'), '本地胶囊文档应声明 legacy zip archive 路径');
  const oldCapsuleDirToken = `capsules_${'v3'}/<name>.capsule/`;
  assert.ok(!localCapsuleDocs.includes(oldCapsuleDirToken), '本地胶囊文档不应继续公开旧试验路径');
  assert.ok(!gptImage2Tool.includes('_run_' + 'legacy' + '_chat_fallback'), 'GptImage2Tool 不应隐藏回退到旧 chat-completions 路径');
  assert.ok(!veo3Tool.includes('已废弃'), 'Veo3 工具 schema 不应保留废弃参数');
  assert.ok(!workspaceManager.includes('旧布局'), 'workspace_manager.py 不应继续扫描旧 workspace 布局');
  assert.ok(!workflowConfig.includes('Compatibility exports'), 'workflow config re-export 不应标记为 compatibility');

  const videoConfig = readFileSync(join(configDir, 'video_engines.yaml'), 'utf-8');
  assert.ok(videoConfig.includes('default: seedance-fast'), '默认视频引擎应为 seedance-fast');
  assert.ok(videoConfig.includes('seedance-fast'), '视频引擎配置应声明 seedance-fast');

  const durationTool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'video_processing', 'video_duration_tool.py'), 'utf-8');
  assert.ok(durationTool.includes('target_visual_duration'), '有配音时不应因旁白短而裁掉分镜目标时长');
  assert.ok(!durationTool.includes('不再被 scene_duration 限制'), '时长策略不应完全忽略分镜目标时长');
  console.log('  ✅ 运行时配置文件验证通过');
}

// 测试 5: SQLite 胶囊仓库脚本
function testCapsuleStoreExists() {
  const capsuleScript = join(SKILL_DIR, 'scripts', 'capsule_store.py');
  assert.ok(existsSync(capsuleScript), 'scripts/capsule_store.py 应存在');
  const capsulesDir = join(SKILL_DIR, 'capsules');
  if (existsSync(capsulesDir)) {
    for (const entry of readdirSync(capsulesDir)) {
      assert.ok(!entry.endsWith('.md'), `capsules/ 只放标准包，不应包含 Markdown 胶囊: ${entry}`);
    }
  }
  console.log('  ✅ SQLite 胶囊仓库脚本验证通过');
}

// 测试 5a: 当前仓库不应继续携带在线数据库导出的历史胶囊参考
function testNoHistoricalOnlineCapsuleReference() {
  const removedReferenceName = ['video', 'workflow', 'online', 'capsule', 'reference'].join('_') + '.json';
  const removedReference = join('capsules', removedReferenceName);
  assert.ok(
    !existsSync(join(SKILL_DIR, removedReference)),
    `${removedReference} 是迁移期输入，不应继续作为当前胶囊来源入仓`
  );

  for (const file of listTextFiles(SKILL_DIR)) {
    const relativePath = relative(SKILL_DIR, file);
    const content = readFileSync(file, 'utf-8');
    assert.ok(
      !content.includes(removedReferenceName),
      `${relativePath} 不应继续引用已移除的在线胶囊参考`
    );
  }

  const removedOnlineNames = [
    ['ai', 'news', 'marketing', 'account'].join('-'),
    ['cinematic', 'cat', 'music', 'mv'].join('-'),
    ['dance', 'action'].join('-') + '_4bac1399',
    ['digital', 'human'].join('-') + '_b02dd8a0',
    ['food', 'video'].join('-') + '_4bac1399',
    ['healing', 'asmr'].join('-') + '_a0db6101',
    ['tech', 'news', 'flash'].join('-') + '_a7ce724a',
    ['viral', 'video', 'breakdown'].join('-'),
  ];
  for (const file of listTextFiles(SKILL_DIR)) {
    const relativePath = relative(SKILL_DIR, file);
    const content = readFileSync(file, 'utf-8');
    for (const name of removedOnlineNames) {
      assert.ok(!content.includes(name), `${relativePath} 不应保留历史在线胶囊名: ${name}`);
    }
  }

  console.log('  ✅ 历史在线胶囊参考清理验证通过');
}

// 测试 5a: 胶囊命名应统一为短名，不保留旧长名入口
function testCapsuleNamesAreCanonicalShortNamesWithoutRemovedNameEntries() {
  const publicFiles = [
    'skill.md',
    'references/local-capsule-sqlite.md',
    'references/tools-api.md',
    'references/production-guide.md',
    'scripts/capsule_store.py',
    'scripts/capsule_runtime.py',
  ];
  const removedPublicNames = [
    ['douyin', 'life', 'sim', 'anime', 'voiceover', 'v1'].join('_'),
    ['github', 'skills', 'showcase'].join('_'),
    ['art', 'frame', 'transition', 'video'].join('_'),
    ['healing', 'asmr', 'food', 'daily', 'v1'].join('_'),
    ['guofeng', 'history', 'explainer'].join('_'),
    ['guofeng', 'historical', 'explainer'].join('_'),
    ['voiceover', 'realistic'].join('_'),
    ['tech', 'news', 'flash', 'local'].join('_'),
  ];

  for (const file of publicFiles) {
    const content = readFileSync(join(SKILL_DIR, file), 'utf-8');
    for (const name of removedPublicNames) {
      assert.ok(!content.includes(name), `${file} 不应公开使用旧/长胶囊名: ${name}`);
    }
  }

  const capsulesDir = join(SKILL_DIR, 'capsules');
  const packageNames = existsSync(capsulesDir)
    ? readdirSync(capsulesDir).filter((name) => name.endsWith('.capsule')).sort()
    : [];
  const packagedCapsuleNames = listPackagedCapsuleNames();
  const readme = readFileSync(join(SKILL_DIR, 'README.md'), 'utf-8');
  const readmeBuiltinCapsules = [...readme.matchAll(/<td width="12%"><code>([^<]+)<\/code><\/td>/g)]
    .map(match => match[1])
    .sort();
  assert.deepStrictEqual(
    readmeBuiltinCapsules,
    packagedCapsuleNames,
    'README 内置胶囊表必须只列出当前 active .capsule 目录短名'
  );
  for (const name of packageNames) {
    assert.ok(!removedPublicNames.some((oldName) => name.includes(oldName)), `胶囊包应使用短名: ${name}`);
    const capsuleName = name.replace(/\.capsule$/, '');
    const manifest = loadCapsulePackageManifest(capsuleName);
    const manifestText = JSON.stringify(manifest);
    const entries = listCapsulePackageEntries(capsuleName);
    assert.strictEqual(manifest.capsule.name, capsuleName, `${name} capsule.yaml name 应与短包名一致`);
    for (const oldName of removedPublicNames) {
      assert.ok(!manifestText.includes(oldName), `${name} manifest 不应保留旧/长胶囊名: ${oldName}`);
      assert.ok(!entries.some(entry => entry.includes(oldName)), `${name} 包内文件名不应保留旧/长胶囊名: ${oldName}`);
    }
  }

  const capsuleSourceDirs = existsSync(capsulesDir)
    ? readdirSync(capsulesDir, { withFileTypes: true }).filter(entry => entry.isDirectory())
    : [];
  for (const entry of capsuleSourceDirs) {
    if (entry.name === '__pycache__') continue;
    assert.ok(
      !removedPublicNames.some((oldName) => entry.name.includes(oldName)),
      `胶囊源码目录应使用短名: ${relative(SKILL_DIR, join(capsulesDir, entry.name))}`
    );
  }

  console.log('  ✅ 公开胶囊短名统一验证通过');
}

// 测试 5b: repo_showcase 应包含视频号社交价值抽象规则
function testGithubSkillsShowcaseWechatSocialValueGate() {
  const manifest = loadCapsulePackageManifest('repo_showcase');
  const capsule = manifest.capsule;
  assert.strictEqual(capsule.name, 'repo_showcase', '应读取 repo_showcase 胶囊');
  const qualityRules = readFileSync(join(SKILL_DIR, 'capsules', 'repo_showcase.capsule', 'quality', 'rules.yaml'), 'utf-8');
  const copyRecipe = readFileSync(join(SKILL_DIR, 'capsules', 'repo_showcase.capsule', 'recipes', 'copy.md'), 'utf-8');
  assert.ok(qualityRules.includes('wechat_social_value_gate_required'), 'repo_showcase 应声明 wechat_social_value_gate_required');
  assert.ok(qualityRules.includes('hard_value'), '视频号价值角度应包含 hard_value');
  assert.ok(qualityRules.includes('distinctive_view'), '视频号价值角度应包含 distinctive_view');
  assert.ok(qualityRules.includes('unexpected_use'), '视频号价值角度应包含 unexpected_use');
  assert.ok(copyRecipe.includes('wechat_social_value_gate'), 'copy recipe 应保留 wechat_social_value_gate 方法名');
  const gateSection = copyRecipe.match(/## wechat_social_value_gate\n([\s\S]*?)\n## /)?.[1] || '';

  const qualityRuleIds = new Set([...qualityRules.matchAll(/^\s*id:\s*([A-Za-z0-9_-]+)/gm)].map(match => match[1]));
  for (const id of [
    'wechat_social_value_gate_required',
    'wechat_no_generic_interaction_copy',
    'wechat_abstract_methodology_boundary',
  ]) {
    assert.ok(qualityRuleIds.has(id), `quality_rules 应包含 ${id}`);
  }

  for (const token of ['Token', 'Agent', '代码质量', '团队流程']) {
    assert.ok(!gateSection.includes(token), `wechat_social_value_gate 不应固化具体样例词: ${token}`);
  }

  console.log('  ✅ GitHub showcase 视频号社交价值规则验证通过');
}

// 测试 6: 脚本文件完整性
function testScriptsExist() {
  const scriptDir = join(SKILL_DIR, 'scripts');
  const expectedScripts = [
    'env_loader.py', 'output_guard.py', 'workspace_manager.py',
    'run_video.py', 'run_tool.py', 'run_scene.py', 'run_concat.py', 'run_language_check.py',
    'score_video_quality.py', 'capsule_store.py', 'local_video_qa.py', 'release_manifest.py',
    'build_edit_plan.py', 'validate_edit_plan.py', 'release_checkpoint.py', 'plan_repairs.py',
    'provider_menu.py',
  ];

  for (const script of expectedScripts) {
    assert.ok(existsSync(join(scriptDir, script)), `scripts/${script} 应存在`);
  }
  console.log('  ✅ 脚本文件完整性验证通过');
}

// 测试 7: capabilities 覆盖所有工作流
function testCapabilitiesCoverage() {
  const content = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');

  const requiredCapabilities = [
    'generate-full-video', 'generate-storyboard', 'generate-image',
    'generate-video-clip', 'generate-tts-audio', 'concatenate-videos',
    'add-subtitles', 'add-background-music', 'check-video-quality',
    'feedback-driven-regeneration', 'detect-video-language',
    'manage-local-capsules', 'generate-music', 'validate-edit-plan',
  ];

  for (const cap of requiredCapabilities) {
    assert.ok(content.includes(`id: ${cap}`), `应包含 capability: ${cap}`);
  }
  console.log('  ✅ capabilities 覆盖验证通过');
}

// 测试 8: 安全性 — index.js 不直接使用 process.env 传递全部变量
async function testSecurityNoProcessEnvLeak() {
  const content = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');

  // 不应出现 ...process.env 透传
  assert.ok(!content.includes('...process.env'), '不应使用 ...process.env 透传环境变量');
  assert.ok(!content.includes('run_upload.py'), '不应包含云上传脚本调用');

  // 应使用 context.env.get
  assert.ok(content.includes('context.env.get'), '应通过 context.env.get() 读取环境变量');

  // 应有 ALLOWED_ENV_KEYS 白名单
  assert.ok(content.includes('ALLOWED_ENV_KEYS'), '应有环境变量白名单');

  console.log('  ✅ 安全性验证通过');
}

// 测试 9: skill.md permissions.env 与 index.js 白名单一致
function testEnvWhitelistConsistency() {
  const registry = loadEnvRegistry();
  const registryKeys = registry.map(entry => entry.key);
  const openclawKeys = registry.filter(entry => entry.openclaw).map(entry => entry.key);
  const skillEnvs = extractSkillEnvs();
  const indexEnvs = extractIndexAllowedEnvs();
  const exampleKeys = extractEnvExampleKeys();

  assert.strictEqual(new Set(registryKeys).size, registryKeys.length, 'env registry 不应包含重复 key');
  assert.ok(openclawKeys.length >= 10, `应至少声明 10 个 OpenClaw 环境变量，实际: ${openclawKeys.length}`);
  assert.deepStrictEqual(sorted(skillEnvs), sorted(openclawKeys), 'skill.md permissions.env 应等于 registry openclaw=true');
  assert.deepStrictEqual(sorted(indexEnvs), sorted(openclawKeys), 'index.js ALLOWED_ENV_KEYS 应等于 registry openclaw=true');
  assert.deepStrictEqual(sorted(exampleKeys), sorted(registryKeys), 'lib/.env.example 应与 registry key 完全一致');
  assert.ok(openclawKeys.includes('ARK_SEEDANCE20_MODEL'), 'Seedance 2.0 模型 env 应可通过 OpenClaw 传入');
  assert.ok(openclawKeys.includes('ARK_BASE_URL'), 'Seedance 2.0 Ark base URL 应可通过 OpenClaw 传入');

  for (const entry of registry) {
    assert.ok(entry.category, `${entry.key} 应声明 category`);
    assert.strictEqual(typeof entry.secret, 'boolean', `${entry.key} 应声明 secret 布尔值`);
    assert.ok(entry.description, `${entry.key} 应声明 description`);
  }

  console.log(`  ✅ 环境变量注册表一致性验证通过 (${registryKeys.length} 个变量)`);
}

// 测试 10: lib/ 目录包含核心 Python 工具模块
function testLibExists() {
  const libDir = join(SKILL_DIR, 'lib');
  assert.ok(existsSync(libDir), 'lib/ 目录应存在');

  const requiredModules = ['custom_tools', 'video_workflows', 'src'];
  for (const mod of requiredModules) {
    assert.ok(existsSync(join(libDir, mod)), `lib/${mod}/ 应存在`);
  }
  const removedRuntimeDir = ['runtime', 'aliases'].join('_');
  assert.ok(!existsSync(join(libDir, removedRuntimeDir)), '旧 runtime alias 目录不应继续保留');
  assert.ok(!lstatSync(join(libDir, 'src')).isSymbolicLink(), 'lib/src 不应是指向本机旧项目的符号链接');

  assert.ok(existsSync(join(libDir, 'requirements.txt')), 'lib/requirements.txt 应存在');
  assert.ok(!existsSync(join(libDir, 'logs')), 'lib/logs 不应进入项目');
  assert.ok(!existsSync(join(libDir, '.env')), 'lib/.env 不应进入项目');

  // 验证 custom_tools 子模块完整
  const expectedToolDirs = [
    'image_generation', 'video_generation', 'audio_generation',
    'video_processing', 'quality_check', 'music_generation',
  ];
  for (const toolDir of expectedToolDirs) {
    assert.ok(
      existsSync(join(libDir, 'custom_tools', toolDir)),
      `lib/custom_tools/${toolDir}/ 应存在`
    );
  }

  console.log('  ✅ lib/ 工具库完整性验证通过');
}

// 测试 10b: runtime generator 实现应只位于 canonical src/runtime
function testRuntimeModuleBoundaries() {
  const runtimeDir = join(SKILL_DIR, 'lib', 'src', 'runtime', 'general_video_crew');
  const modules = ['audio_generator.py', 'image_generator.py', 'video_generator.py', 'post_processor.py'];

  assert.ok(existsSync(runtimeDir), 'canonical runtime 目录应存在');

  for (const mod of modules) {
    const runtimePath = join(runtimeDir, mod);
    assert.ok(existsSync(runtimePath), `runtime/${mod} 应存在`);

    const runtimeContent = readFileSync(runtimePath, 'utf-8');
    assert.ok(runtimeContent.includes('class '), `runtime/${mod} 应包含真实实现`);
  }

  const flowContent = readFileSync(join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'flow.py'), 'utf-8');
  assert.ok(
    flowContent.includes('from src.runtime.general_video_crew.audio_generator import AudioGenerator'),
    'video workflow 应使用 canonical runtime import'
  );
  assert.ok(!flowContent.includes(['runtime', 'aliases'].join('_')), 'video workflow 不应依赖旧 runtime alias import');

  const runtimeInit = readFileSync(join(runtimeDir, '__init__.py'), 'utf-8');
  assert.ok(runtimeInit.includes('def __getattr__'), 'runtime package __init__ 应 lazy export，避免重依赖 eager import');

  const sceneRegenerator = readFileSync(join(runtimeDir, 'scene_regenerator.py'), 'utf-8');
  const runScene = readFileSync(join(SKILL_DIR, 'scripts', 'run_scene.py'), 'utf-8');
  assert.ok(sceneRegenerator.includes('def regenerate_scene'), 'scene_regenerator.py 应提供可复用 regenerate_scene runtime 服务');
  assert.ok(sceneRegenerator.includes('GenerateSceneImageTool'), 'scene regeneration runtime 应复用通用图片生成工具');
  assert.ok(sceneRegenerator.includes('UniversalVideoGenerationTool'), 'scene regeneration runtime 应复用通用视频生成工具');
  assert.ok(
    runScene.includes('from src.runtime.general_video_crew.scene_regenerator import regenerate_scene'),
    'run_scene.py 应调用 canonical scene regeneration runtime'
  );
  assert.ok(!runScene.includes('GenerateSceneImageTool'), 'run_scene.py 不应直接依赖图片生成工具实现');
  assert.ok(!runScene.includes('UniversalVideoGenerationTool'), 'run_scene.py 不应直接依赖视频生成工具实现');

  console.log('  ✅ runtime 模块边界验证通过');
}

// 测试 11: 脚本和入口文件中无硬编码绝对路径
function testNoHardcodedPaths() {
  const filesToCheck = listTextFiles(SKILL_DIR);
  const removedPath = ['/', 'Users', 'june2', 'code', 'github', 'video_workflow'].join('/');

  for (const file of filesToCheck) {
    const content = readFileSync(file, 'utf-8');
    const hasHardcoded = content.includes(removedPath);
    assert.ok(!hasHardcoded, `${file.split('/').pop()} 不应包含硬编码路径`);
    assert.ok(!/sk-[A-Za-z0-9_-]{20,}/.test(content), `${file.split('/').pop()} 不应包含硬编码 API key`);
  }

  console.log('  ✅ 无硬编码路径验证通过');
}

// 测试 12: index.js 使用 ES Module 格式
function testEsModule() {
  const content = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  assert.ok(content.includes('export async function execute'), '应使用 export 导出 execute');
  assert.ok(content.includes("import {") || content.includes("import "), '应使用 import 语法');
  assert.ok(!content.includes('module.exports'), '不应使用 CommonJS module.exports');
  assert.ok(!content.includes("require("), '不应使用 CommonJS require');
  console.log('  ✅ ES Module 格式验证通过');
}

// 测试 13: 文档和 prompt 不应出现已移除能力的具名声明
function testNoRemovedToolDeclarations() {
  const filesToCheck = [
    join(SKILL_DIR, 'skill.md'),
    join(SKILL_DIR, 'openclaw.plugin.json'),
    join(SKILL_DIR, 'package.json'),
    join(SKILL_DIR, 'references', 'tools-api.md'),
    join(SKILL_DIR, 'references', 'engines-and-voices.md'),
    join(SKILL_DIR, 'references', 'video-recipes.md'),
    join(SKILL_DIR, 'lib', 'custom_tools', 'README.md'),
    join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'tasks.py'),
  ];

  const token = (...parts) => parts.join('');
  const removedTokens = [
    token('run_', 'action_', 'transfer.py'),
    token('run_', 'digital_', 'human.py'),
    token('run_', 'novel_', 'manga.py'),
    token('custom_tools.', 'action_', 'animation'),
    token('custom_tools.', 'lip_', 'sync'),
    token('custom_tools.', 'voice_', 'clone'),
    token('custom_tools.', 'content_', 'crawler'),
    token('custom_tools.', 'extract_', 'content'),
    token('veo3_', 'video_', 'generator_', 'tool2'),
    token('jimeng4_', 'image_', 'generator_', 'tool'),
    token('rep_', 'k', 'ling', '26'),
    token('rep_', 'ke', 'ling', '26'),
    token('Rep', 'K', 'ling', '26'),
    token('REPLI', 'CATE', '_API_', 'TOKEN'),
    token('sora', '2'),
    token('hai', 'luo'),
    token('vi', 'du'),
    token('mid', 'journey'),
    token('数字', '人'),
    token('声', '克隆'),
    token('声音', '克隆'),
    token('对', '口型'),
    token('动作', '迁移'),
    token('小说', '漫改'),
    token('平台', '爬虫'),
    token('下', '载', '/爬虫'),
    token('下', '载', '分析'),
    token('复', '刻'),
  ];

  for (const file of filesToCheck) {
    const content = readFileSync(file, 'utf-8');
    for (const token of removedTokens) {
      assert.ok(!content.includes(token), `${file.split('/').pop()} 不应包含旧声明 ${token}`);
    }
  }

  console.log('  ✅ 移除能力具名声明清理验证通过');
}

// 测试 13b: 文档中的 run_tool 示例只能调用注册表内工具
function testToolRecipeExamplesUseRegisteredTools() {
  const registeredTools = loadToolRegistryNames();
  const docsToCheck = [
    join(SKILL_DIR, 'references', 'tool-recipes.md'),
    join(SKILL_DIR, 'references', 'tools-api.md'),
    join(SKILL_DIR, 'references', 'channel-customization.md'),
  ];

  const commandToolPattern = /--tool\s+["']?([A-Za-z][A-Za-z0-9_]*Tool)["']?/g;
  const jsonToolPattern = /"tool"\s*:\s*"([^"]+)"/g;
  for (const file of docsToCheck) {
    const content = readFileSync(file, 'utf-8');
    const toolNames = [
      ...[...content.matchAll(commandToolPattern)].map(match => match[1]),
      ...[...content.matchAll(jsonToolPattern)].map(match => match[1]),
    ].filter(name => !name.includes('[') && !name.includes('<'));
    for (const toolName of toolNames) {
      assert.ok(
        registeredTools.has(toolName),
        `${file.split('/').pop()} 示例调用未注册工具: ${toolName}`
      );
    }
  }

  console.log('  ✅ 文档工具示例注册表验证通过');
}

// 测试 13c: Channel Policy 的 Approved 工具必须在工具注册表中
function testChannelPolicyApprovedToolsAreRegistered() {
  const registeredTools = loadToolRegistryNames();
  const content = readFileSync(join(SKILL_DIR, 'references', 'channel-policy.md'), 'utf-8');
  const approvedContent = content.split('## Do Not Select')[0];
  const toolTokens = new Set([...approvedContent.matchAll(/`([A-Za-z][A-Za-z0-9_]*Tool)`/g)].map(match => match[1]));

  for (const toolName of toolTokens) {
    assert.ok(registeredTools.has(toolName), `channel-policy Approved 工具未注册: ${toolName}`);
  }

  console.log('  ✅ Channel Policy Approved 工具注册表验证通过');
}

// 测试 13d: 核心制作文档应使用标准 release/work/qa/logs 产物布局
function testDocsUseStandardArtifactLayout() {
  const docsToCheck = [
    join(SKILL_DIR, 'skill.md'),
    join(SKILL_DIR, 'references', 'production-guide.md'),
    join(SKILL_DIR, 'references', 'workflow-state-artifacts.md'),
    join(SKILL_DIR, 'references', 'local-script-protocol.md'),
    join(SKILL_DIR, 'references', 'storyboard-schema.md'),
    join(SKILL_DIR, 'references', 'tools-api.md'),
    join(SKILL_DIR, 'references', 'local-capsule-sqlite.md'),
    join(SKILL_DIR, 'references', 'video-review-gate.md'),
  ];
  const forbiddenTokens = [
    'reports/local_video_qa.json',
    'reports/video_quality_score.json',
    '/final/video.mp4',
    '/final/copy.txt',
    'images/`、`audios/`、`videos/`、`final/',
    'output/<run_id>/\n  CURRENT_RELEASE.md',
    'output_path":"/tmp',
    'output_dir":"/tmp',
    '--workspace_dir /path/to/workspace',
    '--run-dir /path/to/workspace',
  ];

  for (const file of docsToCheck) {
    const content = readFileSync(file, 'utf-8');
    for (const token of forbiddenTokens) {
      assert.ok(!content.includes(token), `${file.split('/').pop()} 不应再使用旧产物布局: ${token}`);
    }
  }

  console.log('  ✅ 文档产物布局验证通过');
}

// 测试 14: 默认输出目录应落在仓库 output/，外部覆盖必须被拒绝
function testDefaultOutputRoot() {
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const workspaceManagerContent = readFileSync(join(SKILL_DIR, 'scripts', 'workspace_manager.py'), 'utf-8');
  const workflowContent = readFileSync(join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'crew.py'), 'utf-8');
  const workspaceUtilsContent = readFileSync(join(SKILL_DIR, 'lib', 'src', 'utils', 'workspace_utils.py'), 'utf-8');
  const scriptOutputGuardContent = readFileSync(join(SKILL_DIR, 'scripts', 'output_guard.py'), 'utf-8');
  const libOutputGuardContent = readFileSync(join(SKILL_DIR, 'lib', 'src', 'utils', 'output_paths.py'), 'utf-8');

  assert.ok(
    jsContent.includes("const DEFAULT_OUTPUT_DIR = join(SKILL_DIR, 'output');"),
    'index.js 默认输出目录应为本仓库 output/'
  );
  assert.ok(
    jsContent.includes('requireUnderOutput(') && jsContent.includes("if (key === 'OPENCLAW_OUTPUT_DIR') continue"),
    'index.js 应校验 OPENCLAW_OUTPUT_DIR 且不能被白名单循环覆盖'
  );
  assert.ok(
    workspaceManagerContent.includes('PROJECT_ROOT = Path(__file__).resolve().parents[1]'),
    'workspace_manager.py 项目根应为当前仓库'
  );
  assert.ok(
    workspaceManagerContent.includes('from output_guard import get_output_base_dir'),
    'workspace_manager.py 应通过 output_guard 解析输出根'
  );
  assert.ok(
    workflowContent.includes('workspace_base / f"general_video_{timestamp}"'),
    '主视频流程应在默认输出根下创建 general_video_<timestamp>/ run 目录'
  );
  assert.ok(
    workspaceUtilsContent.includes('from src.utils.output_paths import get_output_base_dir'),
    'WorkspaceManager 应通过 output_paths 解析输出根'
  );
  assert.ok(
    workflowContent.includes('from src.utils.output_paths import get_output_base_dir'),
    '主视频流程应通过 output_paths 解析输出根'
  );
  assert.ok(
    scriptOutputGuardContent.includes('from src.utils.output_paths import') &&
    scriptOutputGuardContent.includes('normalize_output_params'),
    '脚本输出守卫应复用 lib 输出路径逻辑，只保留脚本参数归一化'
  );
  assert.ok(
    libOutputGuardContent.includes('OUTPUT_ROOT = PROJECT_ROOT / "output"') &&
    libOutputGuardContent.includes('must be under'),
    'lib 输出守卫应限制到 output/'
  );

  for (const [name, content] of [
    ['workspace_manager.py', workspaceManagerContent],
    ['workspace_utils.py', workspaceUtilsContent],
    ['crew.py', workflowContent],
  ]) {
    for (const sub of ['release', 'work', 'qa', 'logs']) {
      assert.ok(content.includes(`"${sub}"`) || content.includes(`'${sub}'`), `${name} 应创建 ${sub}/ 子目录`);
    }
  }

  const combined = [workspaceManagerContent, workspaceUtilsContent, workflowContent].join('\n');
  assert.ok(!combined.includes('openclaw-video-output'), '不应再使用 ~/openclaw-video-output 作为默认输出目录');

  console.log('  ✅ 默认输出目录验证通过');
}

// 测试 15: custom_tools 包入口必须保持 lazy，避免导入轻量子模块时加载 CrewAI 全栈
function testCustomToolsLazyImports() {
  const customToolsInit = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', '__init__.py'), 'utf-8');
  const audioInit = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'audio_generation', '__init__.py'), 'utf-8');

  assert.ok(customToolsInit.includes('def __getattr__'), 'custom_tools/__init__.py 应使用 lazy __getattr__');
  assert.ok(audioInit.includes('def __getattr__'), 'audio_generation/__init__.py 应使用 lazy __getattr__');

  const forbiddenTopLevelImports = [
    'from .audio_generation import',
    'from .doubao_tts_tool import',
    'from .tts_tool import',
    'from crewai.tools import',
  ];
  for (const token of forbiddenTopLevelImports) {
    assert.ok(!customToolsInit.includes(token), `custom_tools/__init__.py 不应 eager import: ${token}`);
    assert.ok(!audioInit.includes(token), `audio_generation/__init__.py 不应 eager import: ${token}`);
  }

  assert.ok(
    audioInit.includes('"synthesize_with_minimax": "custom_tools.audio_generation.minimax_tts_tool"'),
    'audio_generation lazy exports 应包含 synthesize_with_minimax'
  );

  console.log('  ✅ custom_tools lazy import 验证通过');
}

// 测试 16: OpenClaw 入口应使用标准 work/release 布局与 storyboard 字段
async function testArtifactCollectionLayoutCompatibility() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  assert.ok(typeof mod.collectWorkspaceArtifacts === 'function', 'index.js 应导出 collectWorkspaceArtifacts 供契约测试');

  const workspace = mkdtempSync(join(tmpdir(), 'capsule-cinema-workspace-'));
  mkdirSync(join(workspace, 'work', 'reference_images'), { recursive: true });
  mkdirSync(join(workspace, 'work', 'images'), { recursive: true });
  mkdirSync(join(workspace, 'work', 'videos'), { recursive: true });
  mkdirSync(join(workspace, 'release'), { recursive: true });

  writeFileSync(
    join(workspace, 'storyboard.json'),
    JSON.stringify({
      storyboard: [
        {
          index: 1,
          description: 'storyboard contract',
          subtitle_text: '字幕',
          duration: 3,
        },
      ],
    }),
    'utf-8',
  );
  writeFileSync(join(workspace, 'work', 'reference_images', 'char.png'), '');
  writeFileSync(join(workspace, 'work', 'images', 'scene_01.png'), '');
  writeFileSync(join(workspace, 'work', 'videos', 'scene_01.mp4'), '');
  writeFileSync(join(workspace, 'release', 'final.mp4'), '');

  const artifacts = mod.collectWorkspaceArtifacts(workspace);
  assert.strictEqual(artifacts.sceneCount, 1, '应从 storyboard 字段读取场景数');
  assert.strictEqual(artifacts.storyboardPreview[0].scene_id, 1, '应保留 index 作为展示 ID');
  assert.ok(artifacts.referenceImages[0].endsWith('work/reference_images/char.png'), '应收集 work/reference_images');
  assert.ok(artifacts.previewImages[0].endsWith('work/images/scene_01.png'), '应收集 work/images');
  assert.ok(artifacts.sceneVideos[0].endsWith('work/videos/scene_01.mp4'), '应收集 work/videos');
  assert.ok(artifacts.finalVideoPath.endsWith('release/final.mp4'), '应从 release/ 收集最终视频');

  console.log('  ✅ artifact 布局验证通过');
}

// 测试 17: 不应为 run_video.py 预创建一个不会被脚本使用的空 workspace
function testWorkspaceCreationOwnership() {
  const content = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  assert.ok(
    content.includes('route.supports_output_dir && !inputs.workspace_dir'),
    'index.js 只应在脚本支持 --output_dir 时预创建 workspace'
  );
  assert.ok(
    !content.includes('const workspace = await createWorkspace(workflow, context);'),
    'index.js 不应无条件预创建 workspace'
  );
  console.log('  ✅ workspace 创建归属验证通过');
}

// 测试 18: 视频引擎支持列表、配置文件和规划 prompt 应保持一致
function testVideoEngineSupportAlignment() {
  const videoConfig = readFileSync(join(SKILL_DIR, 'lib', 'config', 'video_engines.yaml'), 'utf-8');
  const runtimeConfig = readFileSync(join(SKILL_DIR, 'lib', 'src', 'video_generation_config.py'), 'utf-8');
  const videoTool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'video_generation', 'video_generation_tool.py'), 'utf-8');
  const tasks = readFileSync(join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'tasks.py'), 'utf-8');
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const enginesAndVoices = readFileSync(join(SKILL_DIR, 'references', 'engines-and-voices.md'), 'utf-8');

  const expected = ['seedance-fast', 'seedance', 'seedance2.0', 'jimeng35pro', 'veo3', 'veo3.1'];
  const registryNames = loadToolRegistryNames();
  assert.ok(
    registryNames.has('Veo31VideoGeneratorTool'),
    'tool_registry.yaml 应注册 Veo31VideoGeneratorTool'
  );
  for (const engine of expected) {
    assert.ok(videoConfig.includes(engine), `video_engines.yaml 应声明 ${engine}`);
    assert.ok(runtimeConfig.includes(`"${engine}"`), `runtime config 应支持 ${engine}`);
    assert.ok(videoTool.includes(engine), `通用视频工具应支持 ${engine}`);
    assert.ok(tasks.includes(engine), `规划 prompt 应提到 ${engine}`);
    assert.ok(skillContent.includes(engine), `skill.md 应对外声明 ${engine}`);
    assert.ok(enginesAndVoices.includes(`| ${engine} |`), `engines-and-voices.md 应列出 ${engine}`);
  }
  assert.ok(
    runtimeConfig.includes('SUPPORTED_VIDEO_ENGINES') &&
    runtimeConfig.includes('CONFIG.SUPPORTED_VIDEO_ENGINES'),
    'runtime 应区分 supported engines 和 fallback order'
  );

  console.log('  ✅ 视频引擎支持列表对齐验证通过');
}

// 测试 19: feedback 重生成应复用通用图片工具，而不是硬编码单一 provider
function testFeedbackUsesConfigurableImageEngine() {
  const runScene = readFileSync(join(SKILL_DIR, 'scripts', 'run_scene.py'), 'utf-8');
  const imageTool = readFileSync(join(SKILL_DIR, 'lib', 'custom_tools', 'image_generation', 'image_generation_tool.py'), 'utf-8');
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');

  assert.ok(runScene.includes('--image_engine'), 'run_scene.py 应暴露 --image_engine');
  assert.ok(runScene.includes('regenerate_scene'), 'run_scene.py 应通过 runtime service 执行 feedback 重生成');
  assert.ok(sceneRegeneratorIncludesTool(), 'scene_regenerator.py 应复用通用图片生成工具');
  assert.ok(!runScene.includes('from custom_tools.image_generation.gemini3_pro_image_tool import Gemini3ProImageGeneratorTool'), 'run_scene.py 不应硬编码 Gemini 图片工具');
  assert.ok(imageTool.includes('output_path: Optional[str]'), 'GenerateSceneImageTool 应支持精确 output_path');
  assert.ok(jsContent.includes("image_engine:      '--image_engine'"), 'index.js 应透传 image_engine');
  assert.ok(jsContent.includes("skip_image:        { flag: '--skip_image', type: 'boolean' }"), 'index.js 应支持 skip_image 布尔 flag');
  assert.ok(skillContent.includes('name: image_engine') && skillContent.includes('name: skip_image'), 'skill.md 应声明 feedback 图片控制输入');

  console.log('  ✅ feedback 图片引擎可配置验证通过');
}

function sceneRegeneratorIncludesTool() {
  const content = readFileSync(
    join(SKILL_DIR, 'lib', 'src', 'runtime', 'general_video_crew', 'scene_regenerator.py'),
    'utf-8'
  );
  return content.includes('GenerateSceneImageTool');
}

// 测试 20: OpenClaw 适配层不应在 JS 中硬编码 provider 密钥预检
function testAdapterAvoidsProviderSecretPreflight() {
  const content = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');

  assert.ok(content.includes("'concat':"), 'index.js 应注册 concat workflow');
  assert.ok(content.includes("workflow === 'concat' && !inputs.workspace_dir"), 'concat workflow 应校验 workspace_dir');
  assert.ok(!content.includes('缺少 Gemini API 密钥'), 'index.js 不应无条件要求 Gemini 密钥');
  assert.ok(!content.includes('const geminiKey'), 'index.js 不应硬编码 Gemini 预检');
  assert.ok(!content.includes('缺少必要环境变量 CREW_API_KEY'), 'index.js 不应绕过 DOTENV_PATH 预检 CREW_API_KEY');
  assert.ok(content.includes("'KRILL_GPT_IMAGE2_API_KEY'"), 'index.js 应允许 Krill GPT Image 2 API key 传入子进程');
  assert.ok(content.includes("'KRILL_GPT_IMAGE2_BASE_URL'"), 'index.js 应允许 Krill GPT Image 2 base URL 传入子进程');

  console.log('  ✅ 适配层 provider 预检边界验证通过');
}

// 测试 21: 主视频流程应保留 prompt 快照、scene 产物路径和自动 QA 闭环
function testRuntimeTraceabilityArtifacts() {
  const flow = readFileSync(join(SKILL_DIR, 'lib', 'video_workflows', 'general_video', 'flow.py'), 'utf-8');
  const runVideo = readFileSync(join(SKILL_DIR, 'scripts', 'run_video.py'), 'utf-8');
  const planRepairs = readFileSync(join(SKILL_DIR, 'scripts', 'plan_repairs.py'), 'utf-8');
  const providerMenu = readFileSync(join(SKILL_DIR, 'scripts', 'provider_menu.py'), 'utf-8');
  const productionContract = readFileSync(join(SKILL_DIR, 'lib', 'src', 'contracts', 'production_contract.py'), 'utf-8');

  assert.ok(flow.includes('def _write_prompt_snapshots'), 'flow.py 应写 prompts/ 快照');
  assert.ok(flow.includes("prompt_index.json"), 'flow.py 应写 prompts/prompt_index.json');
  assert.ok(flow.includes("'storyboard_prompt'"), 'artifact_manifest 应登记 prompt 快照');
  assert.ok(flow.includes('def _update_storyboard_artifact_paths'), 'flow.py 应回写 scene 产物路径');
  for (const field of ['audio_path', 'image_path', 'raw_video_path', 'subtitled_video_path', 'video_path']) {
    assert.ok(flow.includes(`'${field}'`), `storyboard 应记录 ${field}`);
  }
  for (const category of ['storyboard_image', 'scene_video', 'voiceover', 'character_ref', 'bgm']) {
    assert.ok(flow.includes(`'${category}'`), `artifact_manifest 应登记 ${category}`);
  }

  assert.ok(runVideo.includes('run_local_video_qa'), 'run_video.py 应自动运行本地 QA');
  assert.ok(runVideo.includes('write_edit_plan_validation'), 'run_video.py 应自动校验 edit_plan');
  assert.ok(runVideo.includes('require_prompts=True'), '本地 QA 应要求 prompt 快照');
  assert.ok(runVideo.includes('write_repair_plan'), 'run_video.py 应自动生成 repair_plan');
  assert.ok(runVideo.includes('write_release_checkpoint'), 'run_video.py 应自动生成 release_checkpoint');
  assert.ok(runVideo.includes('build_delivery_promise'), 'run_video.py 应生成 delivery_promise');
  assert.ok(runVideo.includes('write_production_proposal'), 'run_video.py 应写 work/production_proposal.json');
  assert.ok(runVideo.includes('append_decision'), 'run_video.py 应写 work/decision_log.json');
  assert.ok(runVideo.includes('delivery_promise'), 'run_video.py 应把 delivery_promise 写入结果/产物');
  assert.ok(flow.includes("'delivery_promise': kwargs.get('delivery_promise')"), 'flow.py 应保留 delivery_promise 到运行状态');
  assert.ok(flow.includes("'delivery_promise': self.state.get('delivery_promise')"), 'artifact_manifest 应记录 delivery_promise');
  assert.ok(planRepairs.includes('local_video_qa.json'), 'plan_repairs.py 应能从 local_video_qa 兜底生成修复计划');
  assert.ok(planRepairs.includes('edit_plan_validation.json'), 'plan_repairs.py 应能从 edit_plan_validation 生成修复计划');
  assert.ok(providerMenu.includes('capsule_cinema.provider_menu.v1'), 'provider_menu.py 应输出 provider menu schema');
  assert.ok(productionContract.includes('capsule_cinema.decision_log.v1'), 'production_contract 应定义 decision_log schema');

  console.log('  ✅ 运行时可追溯产物验证通过');
}

// 测试 21b: OpenClaw 入口和文档应暴露生产契约参数与产物
async function testProductionContractOpenClawSurface() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const toolsApi = readFileSync(join(SKILL_DIR, 'references', 'tools-api.md'), 'utf-8');

  for (const [input, flag] of [
    ['delivery_promise', '--delivery_promise'],
    ['source_review_path', '--source_review_path'],
    ['reference_analysis_path', '--reference_analysis_path'],
    ['accept_preflight_changes', '--accept_preflight_changes'],
  ]) {
    assert.ok(jsContent.includes(`${input}:`), `index.js SCRIPT_PARAM_MAP 应透传 ${input}`);
    assert.ok(jsContent.includes(`'${flag}'`), `index.js SCRIPT_PARAM_MAP 应透传 ${flag}`);
    assertSkillDeclaresIo(input, 'inputs');
    assert.ok(toolsApi.includes(flag), `tools-api.md 应记录 ${flag}`);
  }

  for (const output of [
    'delivery_promise',
    'production_proposal_path',
    'decision_log_path',
    'artifact_manifest_path',
    'release_checkpoint_path',
    'deliverable',
    'run_status',
    'qa_blockers',
  ]) {
    assertSkillDeclaresIo(output, 'outputs');
  }

  assert.ok(toolsApi.includes('scripts/provider_menu.py --json'), 'tools-api.md 应记录 provider menu 入口');
  assert.ok(toolsApi.includes('work/production_proposal.json'), 'tools-api.md 应记录 production proposal 产物');
  assert.ok(toolsApi.includes('work/decision_log.json'), 'tools-api.md 应记录 decision log 产物');

  assert.ok(typeof mod.parseOutput === 'function', 'index.js 应导出 parseOutput 供契约测试');
  const parsed = mod.parseOutput(`log line\n${JSON.stringify({
    final_video: '/tmp/final.mp4',
    workspace_dir: '/tmp/workspace',
    delivery_promise: { promise_type: 'tts_led_explainer' },
    production_proposal_path: '/tmp/workspace/work/production_proposal.json',
    decision_log_path: '/tmp/workspace/work/decision_log.json',
    artifact_manifest_path: '/tmp/workspace/artifact_manifest.json',
    release_checkpoint_path: '/tmp/workspace/release/release_checkpoint.json',
    deliverable: false,
    run_status: 'generated_but_failed_qa',
    qa_blockers: ['local_video_qa_failed'],
    generation_summary: { total_scenes: 3 },
    post_run_warnings: ['review release checkpoint'],
  })}`);

  assert.strictEqual(parsed.video_path, '/tmp/final.mp4');
  assert.strictEqual(parsed.delivery_promise.promise_type, 'tts_led_explainer');
  assert.ok(parsed.production_proposal_path.endsWith('production_proposal.json'));
  assert.ok(parsed.decision_log_path.endsWith('decision_log.json'));
  assert.ok(parsed.artifact_manifest_path.endsWith('artifact_manifest.json'));
  assert.ok(parsed.release_checkpoint_path.endsWith('release_checkpoint.json'));
  assert.strictEqual(parsed.deliverable, false);
  assert.strictEqual(parsed.run_status, 'generated_but_failed_qa');
  assert.deepStrictEqual(parsed.qa_blockers, ['local_video_qa_failed']);
  assert.deepStrictEqual(parsed.post_run_warnings, ['review release checkpoint']);

  console.log('  ✅ OpenClaw 生产契约接口验证通过');
}

// 测试 21c: full-video 进度事件应可从 stdout 中解析，且不误读最终结果 JSON
async function testProgressEventParsing() {
  const mod = await import(join(SKILL_DIR, 'index.js'));
  assert.ok(typeof mod.extractProgressEvents === 'function', 'index.js 应导出 extractProgressEvents');
  assert.ok(typeof mod.extractWorkspaceFromProgress === 'function', 'index.js 应导出 extractWorkspaceFromProgress');

  const text = [
    'log line',
    '{"event":"workspace_created","workspace_dir":"/tmp/capsule/output/general_video_1"}',
    '{"success":true,"workspace_dir":"/tmp/final"}',
  ].join('\n');

  const events = mod.extractProgressEvents(text);
  assert.strictEqual(events.length, 1, '只应提取 event JSON，不应把最终结果当 progress event');
  assert.strictEqual(events[0].event, 'workspace_created');
  assert.strictEqual(
    mod.extractWorkspaceFromProgress(text),
    '/tmp/capsule/output/general_video_1'
  );

  console.log('  ✅ progress event 解析验证通过');
}

// 测试 22: agent-facing skill 文档应保留 superpower 风格的操作契约
function testSkillOperatingContractDocs() {
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const productionGuide = readFileSync(join(SKILL_DIR, 'references', 'production-guide.md'), 'utf-8');
  const capsulePackageFormat = readFileSync(join(SKILL_DIR, 'references', 'capsule-package-format.md'), 'utf-8');

  assert.ok(skillContent.includes('## Agent Operating Contract'), 'skill.md 应包含 Agent Operating Contract');
  assert.ok(
    skillContent.includes('read `references/production-guide.md` before planning'),
    'skill.md 应要求视频制作前读取 production guide'
  );
  assert.ok(
    skillContent.includes('load the active capsule package from `capsules/<name>.capsule/` before planning'),
    'skill.md 应要求胶囊任务优先读取 active 目录包'
  );
  assert.ok(
    skillContent.includes('choose tools only after reading the active channel policy, `lib/config/tool_capabilities.yaml`, and `lib/config/tool_registry.yaml`'),
    'skill.md 应要求按 channel policy、tool capabilities 和 tool registry 选择工具'
  );
  assert.ok(
    productionGuide.includes('Use `lib/config/tool_capabilities.yaml` for capability fit and provider requirements; use `lib/config/tool_registry.yaml` only as the direct invocation/module registry.'),
    'production-guide 应区分能力库和直接调用注册表'
  );
  assert.ok(
    skillContent.includes('do not describe the run as complete'),
    'skill.md 应禁止有 blocker 时声称完成'
  );
  assert.ok(
    skillContent.includes('runtime proposal artifact is an audit record, not a substitute for pre-run proposal review'),
    'skill.md 应澄清运行时 proposal 产物不能替代预运行确认'
  );
  assert.ok(
    skillContent.includes('Capsule tool confirmation first: before generating with a capsule'),
    'skill.md 应要求胶囊生成前确认胶囊内部最终工具链'
  );
  assert.ok(
    skillContent.includes('confirm the final in-capsule tool chain with the user'),
    'skill.md 应明确确认对象是胶囊内部工具链'
  );
  assert.ok(
    productionGuide.includes('The automatic `work/production_proposal.json` written by `scripts/run_video.py` is an audit artifact once a workspace exists; it is not a substitute for pre-run user approval.'),
    'production-guide 应澄清自动 proposal 产物和 proposal gate 的边界'
  );
  assert.ok(
    productionGuide.includes('Capsule tool confirmation is required before generation'),
    'production-guide 应要求胶囊生成前工具确认'
  );
  assert.ok(
    productionGuide.includes('Confirm tools inside the selected capsule, not replacement capsules.'),
    'production-guide 应明确不是推荐替代胶囊'
  );
  assert.ok(
    skillContent.includes('Capsule update conflict gate'),
    'skill.md 应要求 active 胶囊更新前做冲突审查'
  );
  assert.ok(
    skillContent.includes('Structural validation is not a substitute for semantic conflict review'),
    'skill.md 应区分结构校验和语义冲突审查'
  );
  assert.ok(
    productionGuide.includes('conflict review before updating an active capsule'),
    'production-guide 应要求 active 胶囊更新前冲突审查'
  );
  assert.ok(
    capsulePackageFormat.includes('--conflict-resolution'),
    'capsule-package-format 应记录冲突解决确认参数'
  );
  assert.ok(
    capsulePackageFormat.includes('--conflict-report-json'),
    'capsule-package-format 应记录冲突报告参数'
  );

  assert.ok(productionGuide.includes('## Iron Laws'), 'production-guide 应包含 Iron Laws');
  for (const law of [
    'NO FINAL VIDEO DELIVERY WITHOUT A RELEASE CHECKPOINT',
    'NO UNAPPROVED CHANNEL FALLBACK',
    'NO REFERENCE REMAKE WITHOUT SOURCE ANALYSIS',
    'NO CAPSULE PLANNING WITHOUT CONTRACT INSPECTION',
    'NO CAPSULE GENERATION WITHOUT IN-CAPSULE TOOL CONFIRMATION',
  ]) {
    assert.ok(productionGuide.includes(law), `production-guide 应包含铁律: ${law}`);
  }

  console.log('  ✅ skill 操作契约文档验证通过');
}

// 运行所有测试
console.log('Capsule Cinema OpenClaw Skill 测试\n');

const tests = [
  ['skill.md 结构', testSkillMdExists],
  ['index.js 导出', testIndexJsExports],
  ['package.json 格式', testPackageJson],
  ['OpenClaw SDK optional peer', testOpenClawSdkPeerIsOptionalForCiInstall],
  ['测试资产入仓策略', testTestsDirectoryIsVersionable],
  ['元数据对齐', testMetadataAlignment],
  ['引用文件完整性', testReferencesExist],
  ['运行时配置文件', testRuntimeConfigExists],
  ['SQLite 胶囊仓库脚本', testCapsuleStoreExists],
  ['历史在线胶囊参考清理', testNoHistoricalOnlineCapsuleReference],
  ['公开胶囊短名统一', testCapsuleNamesAreCanonicalShortNamesWithoutRemovedNameEntries],
  ['脚本文件完整性', testScriptsExist],
  ['GitHub showcase 视频号社交价值规则', testGithubSkillsShowcaseWechatSocialValueGate],
  ['capabilities 覆盖', testCapabilitiesCoverage],
  ['安全性检查', testSecurityNoProcessEnvLeak],
  ['环境变量白名单一致性', testEnvWhitelistConsistency],
  ['lib/ 工具库完整性', testLibExists],
  ['runtime 模块边界', testRuntimeModuleBoundaries],
  ['无硬编码路径', testNoHardcodedPaths],
  ['ES Module 格式', testEsModule],
  ['移除能力具名声明清理', testNoRemovedToolDeclarations],
  ['文档工具示例注册表', testToolRecipeExamplesUseRegisteredTools],
  ['Channel Policy 工具注册表', testChannelPolicyApprovedToolsAreRegistered],
  ['文档产物布局', testDocsUseStandardArtifactLayout],
  ['默认输出目录', testDefaultOutputRoot],
  ['custom_tools lazy import', testCustomToolsLazyImports],
  ['artifact 布局', testArtifactCollectionLayoutCompatibility],
  ['workspace 创建归属', testWorkspaceCreationOwnership],
  ['视频引擎支持列表对齐', testVideoEngineSupportAlignment],
  ['feedback 图片引擎可配置', testFeedbackUsesConfigurableImageEngine],
  ['适配层 provider 预检边界', testAdapterAvoidsProviderSecretPreflight],
  ['运行时可追溯产物', testRuntimeTraceabilityArtifacts],
  ['OpenClaw 生产契约接口', testProductionContractOpenClawSurface],
  ['progress event 解析', testProgressEventParsing],
  ['skill 操作契约文档', testSkillOperatingContractDocs],
];

let passed = 0;
let failed = 0;

for (const [name, fn] of tests) {
  try {
    await fn();
    passed++;
  } catch (err) {
    console.log(`  ❌ ${name}: ${err.message}`);
    failed++;
  }
}

console.log(`\n结果: ${passed} 通过, ${failed} 失败`);
process.exit(failed > 0 ? 1 : 0);
