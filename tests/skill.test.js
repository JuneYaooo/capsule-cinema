// tests/skill.test.js — Capsule Cinema OpenClaw Skill 基础测试
import assert from 'assert';
import { resolve, join, dirname } from 'path';
import { existsSync, readFileSync, readdirSync, lstatSync } from 'fs';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, '..');

function listTextFiles(dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '__pycache__') continue;
      files.push(...listTextFiles(fullPath));
    } else if (/\.(py|js|json|md|yaml|yml)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
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
  assert.ok(pkg.name, '应包含 name');
  assert.ok(pkg.version, '应包含 version');
  assert.ok(pkg.main === 'index.js', 'main 应为 index.js');
  assert.ok(pkg.type === 'module', 'type 应为 module');
  assert.ok(pkg.peerDependencies?.['@openclaw/skill-sdk'], '应声明 @openclaw/skill-sdk peerDependency');
  console.log('  ✅ package.json 验证通过');
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

  for (const file of expectedFiles) {
    assert.ok(existsSync(join(configDir, file)), `lib/config/${file} 应存在`);
  }
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

// 测试 6: 脚本文件完整性
function testScriptsExist() {
  const scriptDir = join(SKILL_DIR, 'scripts');
  const expectedScripts = [
    'run_video.py', 'run_tool.py', 'run_scene.py', 'run_concat.py', 'run_language_check.py',
    'capsule_store.py', 'local_video_qa.py',
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
    'manage-local-capsules', 'generate-music',
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
  const skillContent = readFileSync(join(SKILL_DIR, 'skill.md'), 'utf-8');
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');

  // 从 skill.md 提取 env 列表（跳过注释行）
  const envSection = skillContent.match(/  env:\n([\s\S]*?)\n\ninputs:/);
  assert.ok(envSection, 'skill.md 应包含 env 列表');
  const skillEnvs = envSection[1]
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('- ') && !line.startsWith('- #'))
    .map(line => line.replace('- ', ''));

  assert.ok(skillEnvs.length >= 10, `应至少声明 10 个环境变量，实际: ${skillEnvs.length}`);

  // 验证每个 skill.md 中声明的变量都在 index.js 白名单中
  for (const key of skillEnvs) {
    assert.ok(jsContent.includes(`'${key}'`), `index.js 白名单应包含 ${key}`);
  }

  console.log(`  ✅ 环境变量白名单一致性验证通过 (${skillEnvs.length} 个变量)`);
}

// 测试 10: lib/ 目录包含核心 Python 工具模块
function testLibExists() {
  const libDir = join(SKILL_DIR, 'lib');
  assert.ok(existsSync(libDir), 'lib/ 目录应存在');

  const requiredModules = ['custom_tools', 'agents', 'agno_agents', 'src'];
  for (const mod of requiredModules) {
    assert.ok(existsSync(join(libDir, mod)), `lib/${mod}/ 应存在`);
  }
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

// 测试 11: 脚本和入口文件中无硬编码绝对路径
function testNoHardcodedPaths() {
  const filesToCheck = listTextFiles(SKILL_DIR);
  const legacyPath = ['/', 'Users', 'june2', 'code', 'github', 'video_workflow'].join('/');

  for (const file of filesToCheck) {
    const content = readFileSync(file, 'utf-8');
    const hasHardcoded = content.includes(legacyPath);
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
    join(SKILL_DIR, 'lib', 'agno_agents', 'general_video_crew', 'tasks.py'),
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
    token('see', 'dance'),
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

// 测试 14: 默认输出目录应落在仓库根 output/，不能落进 skill 包内 output/
function testDefaultOutputRoot() {
  const jsContent = readFileSync(join(SKILL_DIR, 'index.js'), 'utf-8');
  const workspaceManagerContent = readFileSync(join(SKILL_DIR, 'scripts', 'workspace_manager.py'), 'utf-8');
  const agnoCrewContent = readFileSync(join(SKILL_DIR, 'lib', 'agno_agents', 'general_video_crew', 'crew.py'), 'utf-8');
  const workspaceUtilsContent = readFileSync(join(SKILL_DIR, 'lib', 'src', 'utils', 'workspace_utils.py'), 'utf-8');

  assert.ok(
    jsContent.includes("const DEFAULT_OUTPUT_DIR = join(REPO_ROOT, 'output');"),
    'index.js 默认输出目录应为仓库根 output/'
  );
  assert.ok(
    jsContent.includes('|| process.env.OPENCLAW_OUTPUT_DIR') && jsContent.includes('|| DEFAULT_OUTPUT_DIR'),
    'index.js 应注入默认 OPENCLAW_OUTPUT_DIR，并允许环境变量覆盖'
  );
  assert.ok(
    workspaceManagerContent.includes('DEFAULT_OUTPUT_BASE_DIR = PROJECT_ROOT / "output"'),
    'workspace_manager.py 默认输出目录应为仓库根 output/'
  );
  assert.ok(
    agnoCrewContent.includes('workspace_base / f"general_video_agno_{timestamp}"'),
    'Agno 主流程应在默认输出根下创建 general_video_agno_<timestamp>/ run 目录'
  );
  assert.ok(
    workspaceUtilsContent.includes('DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"'),
    'WorkspaceManager 默认输出目录应为仓库根 output/'
  );

  for (const [name, content] of [
    ['workspace_manager.py', workspaceManagerContent],
    ['workspace_utils.py', workspaceUtilsContent],
    ['crew.py', agnoCrewContent],
  ]) {
    for (const sub of ['release', 'work', 'qa', 'logs']) {
      assert.ok(content.includes(`"${sub}"`) || content.includes(`'${sub}'`), `${name} 应创建 ${sub}/ 子目录`);
    }
  }

  const combined = [workspaceManagerContent, workspaceUtilsContent, agnoCrewContent].join('\n');
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

// 运行所有测试
console.log('Capsule Cinema OpenClaw Skill 测试\n');

const tests = [
  ['skill.md 结构', testSkillMdExists],
  ['index.js 导出', testIndexJsExports],
  ['package.json 格式', testPackageJson],
  ['引用文件完整性', testReferencesExist],
  ['运行时配置文件', testRuntimeConfigExists],
  ['SQLite 胶囊仓库脚本', testCapsuleStoreExists],
  ['脚本文件完整性', testScriptsExist],
  ['capabilities 覆盖', testCapabilitiesCoverage],
  ['安全性检查', testSecurityNoProcessEnvLeak],
  ['环境变量白名单一致性', testEnvWhitelistConsistency],
  ['lib/ 工具库完整性', testLibExists],
  ['无硬编码路径', testNoHardcodedPaths],
  ['ES Module 格式', testEsModule],
  ['移除能力具名声明清理', testNoRemovedToolDeclarations],
  ['默认输出目录', testDefaultOutputRoot],
  ['custom_tools lazy import', testCustomToolsLazyImports],
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
