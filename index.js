// index.js — Capsule Cinema OpenClaw Skill 主逻辑入口
// 调用 lib/ 下的 Python 工具库完成视频创作

import { spawn } from 'child_process';
import { existsSync, readdirSync, readFileSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Skill 内部目录结构（自包含，无外部依赖）
const SKILL_DIR = resolve(__dirname);
const REPO_ROOT = dirname(SKILL_DIR);
const LIB_DIR = join(SKILL_DIR, 'lib');        // Python 工具库（custom_tools, agents, agno_agents）
const SCRIPTS_DIR = join(SKILL_DIR, 'scripts'); // 封装脚本
const DEFAULT_OUTPUT_DIR = join(REPO_ROOT, 'output');

/**
 * skill.md permissions.env 中声明的环境变量白名单
 * 只有这些变量会传递给子进程，防止泄露其他敏感信息
 */
const ALLOWED_ENV_KEYS = [
  // Skill 运行时配置
  'PYTHON_BIN', 'DOTENV_PATH', 'VIDEO_RESOURCES_PATH', 'OPENCLAW_OUTPUT_DIR',
  // 即梦 / Seedream
  'JULING_BASE_URL', 'JULING_API_KEY',
  // Veo3
  'VEO3_BASE_URL', 'VEO3_API_KEY', 'VEO_ACCESS_TOKEN',
  // Gemini
  'GEMEINI_IMAGE_MODEL_BASE_URL', 'GEMEINI_IMAGE_MODEL_API_KEY',
  'GEMINI_ANALYSIS_API_BASE_URL', 'GEMINI3_API_KEY', 'GEMINI3_BASE_URL',
  'GEMINI3_PRO_BASE_URL', 'GEMINI3_PRO_API_KEY',
  'VIDEO_ANALYSIS_API_KEY', 'VIDEO_ANALYSIS_BASE_URL',
  // LLM 规划
  'CREW_API_KEY', 'CREW_BASE_URL', 'CREW_MODEL_NAME',
  // TTS
  'DOUBAO_TTS_APPID', 'DOUBAO_TTS_ACCESS_TOKEN', 'DOUBAO_TTS_SECRET_KEY',
  'DOUBAO_ARK_API_KEY', 'DOUBAO_TTS_CLUSTER_ID',
  // 音乐
  'SUNO_BASE_URL', 'SUNO_API_KEY',
  // RunningHub
  'RUNNINGHUB_API_KEY', 'WANANIMATE2_API_KEY', 'WANANIMATE2_WEBAPP_ID',
  'WAN22_API_KEY', 'WAN22_WEBAPP_ID',
  // 语音转录
  'SILICONFLOW_API_KEY', 'SILICONFLOW_API_BASE',
  // 多模态 / 审核
  'MULTIMODAL_API_KEY', 'MULTIMODAL_BASE_URL',
  'MODERATION_API_KEY', 'MODERATION_BASE_URL', 'MODERATION_MODEL_NAME',
  'OPENAI_BASE_URL', 'OPENAI_API_KEY',
  // 本地胶囊仓库
  'VIDEO_CAPSULE_DB', 'VIDEO_PRODUCTION_CAPSULE_DB',
];

/**
 * 意图路由表
 * supports_output_dir: 该脚本是否接受 --output_dir 参数
 */
const WORKFLOW_ROUTES = {
  'full-video':          { script: 'run_video.py',           workflow: 'A', supports_output_dir: false },
  'storyboard-only':     { script: 'run_video.py',           workflow: 'B', supports_output_dir: false, storyboard_only: true },
  'feedback':            { script: 'run_scene.py',           workflow: 'D', supports_output_dir: false },
};

/**
 * 各脚本支持的参数映射（只传递脚本实际接受的参数）
 */
const SCRIPT_PARAM_MAP = {
  'run_video.py': {
    user_requirements: '--user_requirements',
    target_duration:   '--target_duration',
    aspect_ratio:      '--aspect_ratio',
    video_engine:      '--video_engine',
    bgm_path:          '--background_music_path',
  },
  'run_scene.py': {
    workspace_dir:     '--workspace_dir',
    scene_id:          '--scene_id',
    image_prompt:      '--image_prompt',
    video_prompt:      '--video_prompt',
    video_engine:      '--video_engine',
    aspect_ratio:      '--aspect_ratio',
  },
  'run_concat.py': {
    workspace_dir:     '--workspace_dir',
  },
};

/**
 * 自动推断工作流类型
 */
function inferWorkflow(inputs) {
  const { workflow, workspace_dir } = inputs;

  if (workflow && workflow !== 'auto') {
    return workflow;
  }

  if (workspace_dir) return 'feedback';
  return 'full-video';
}

/**
 * 构建 Python 命令行参数（只传递目标脚本实际支持的参数）
 */
function buildArgs(script, inputs) {
  const args = [];
  const paramMap = SCRIPT_PARAM_MAP[script] || {};

  for (const [inputKey, flag] of Object.entries(paramMap)) {
    const value = inputs[inputKey];
    if (value !== undefined && value !== null && value !== '') {
      args.push(flag, String(value));
    }
  }

  return args;
}

/**
 * 从 OpenClaw context 安全地构建子进程环境变量
 */

function safeListFiles(dir, exts = null) {
  if (!dir || !existsSync(dir)) return [];
  try {
    return readdirSync(dir)
      .filter((name) => {
        if (!exts || exts.length === 0) return true;
        return exts.some((ext) => name.toLowerCase().endsWith(ext));
      })
      .sort()
      .map((name) => join(dir, name));
  } catch {
    return [];
  }
}

function loadStoryboardSummary(storyboardPath) {
  if (!storyboardPath || !existsSync(storyboardPath)) {
    return { sceneCount: null, storyboardPreview: [] };
  }

  try {
    const data = JSON.parse(readFileSync(storyboardPath, 'utf-8'));
    const scenes = Array.isArray(data.storyboard) ? data.storyboard : [];
    const preview = scenes.slice(0, 3).map((scene, idx) => ({
      scene_id: scene.scene_id ?? idx,
      description: scene.description || '无描述',
      narration: scene.narration || null,
      subtitle: scene.subtitle || null,
      duration: scene.duration || 0,
    }));
    return {
      sceneCount: scenes.length || null,
      storyboardPreview: preview,
    };
  } catch {
    return { sceneCount: null, storyboardPreview: [] };
  }
}

function collectWorkspaceArtifacts(workspaceDir) {
  if (!workspaceDir) {
    return {
      storyboardPath: null,
      sceneCount: null,
      storyboardPreview: [],
      referenceImages: [],
      previewImages: [],
      sceneVideos: [],
      finalVideos: [],
      latestPreviewImage: null,
      latestSceneVideo: null,
      finalVideoPath: null,
    };
  }

  const storyboardPath = join(workspaceDir, 'storyboard.json');
  const referenceImages = safeListFiles(join(workspaceDir, 'reference_images'), ['.jpg', '.jpeg', '.png', '.webp', '.bmp']);
  const previewImages = safeListFiles(join(workspaceDir, 'images'), ['.jpg', '.jpeg', '.png', '.webp', '.bmp']);
  const sceneVideos = safeListFiles(join(workspaceDir, 'videos'), ['.mp4', '.mov', '.avi', '.mkv', '.webm']);
  const finalVideos = safeListFiles(join(workspaceDir, 'final'), ['.mp4', '.mov', '.avi', '.mkv', '.webm']);
  const storyboardSummary = loadStoryboardSummary(storyboardPath);

  return {
    storyboardPath: existsSync(storyboardPath) ? storyboardPath : null,
    sceneCount: storyboardSummary.sceneCount,
    storyboardPreview: storyboardSummary.storyboardPreview,
    referenceImages,
    previewImages,
    sceneVideos,
    finalVideos,
    latestPreviewImage: previewImages[0] || null,
    latestSceneVideo: sceneVideos[sceneVideos.length - 1] || null,
    finalVideoPath: finalVideos[0] || null,
  };
}

function buildProgressText(snapshot) {
  const parts = [];
  if (snapshot.storyboardPath) {
    const suffix = snapshot.sceneCount ? `（${snapshot.sceneCount} 个场景）` : '';
    parts.push(`分镜已生成${suffix}`);
  }
  if (snapshot.referenceImages.length > 0) {
    parts.push(`角色/风格参考图 ${snapshot.referenceImages.length} 张`);
  }
  if (snapshot.previewImages.length > 0) {
    const total = snapshot.sceneCount ? `/${snapshot.sceneCount}` : '';
    parts.push(`场景图 ${snapshot.previewImages.length}${total} 张`);
  }
  if (snapshot.sceneVideos.length > 0) {
    const total = snapshot.sceneCount ? `/${snapshot.sceneCount}` : '';
    parts.push(`分镜视频 ${snapshot.sceneVideos.length}${total} 条`);
  }
  if (snapshot.finalVideoPath) {
    parts.push('最终成片已生成');
  }
  return parts.join('，');
}

function startWorkspaceMonitor(workspaceDir, context) {
  if (!workspaceDir || !context?.sendProgressUpdate) {
    return { stop() {} };
  }

  let lastSignature = '';
  let lastMilestones = {
    storyboard: false,
    reference: 0,
    images: 0,
    videos: 0,
    final: false,
  };

  const emitSnapshot = () => {
    const snapshot = collectWorkspaceArtifacts(workspaceDir);
    const signature = JSON.stringify({
      storyboard: !!snapshot.storyboardPath,
      reference: snapshot.referenceImages.length,
      images: snapshot.previewImages.length,
      videos: snapshot.sceneVideos.length,
      final: !!snapshot.finalVideoPath,
    });

    if (signature === lastSignature) return;
    lastSignature = signature;

    const messages = [];
    if (snapshot.storyboardPath && !lastMilestones.storyboard) {
      lastMilestones.storyboard = true;
      const title = snapshot.sceneCount ? `分镜文案已完成（${snapshot.sceneCount} 个场景）` : '分镜文案已完成';
      messages.push(title);
      if (snapshot.storyboardPreview.length > 0) {
        const preview = snapshot.storyboardPreview
          .map((scene) => `#${scene.scene_id}: ${scene.description}`)
          .join('\n');
        messages.push(`分镜预览：\n${preview}`);
      }
    }
    if (snapshot.referenceImages.length > lastMilestones.reference) {
      lastMilestones.reference = snapshot.referenceImages.length;
      messages.push(`角色/风格参考图已生成 ${snapshot.referenceImages.length} 张`);
    }
    if (snapshot.previewImages.length > lastMilestones.images) {
      lastMilestones.images = snapshot.previewImages.length;
      const total = snapshot.sceneCount ? `/${snapshot.sceneCount}` : '';
      messages.push(`场景图已生成 ${snapshot.previewImages.length}${total} 张`);
    }
    if (snapshot.sceneVideos.length > lastMilestones.videos) {
      lastMilestones.videos = snapshot.sceneVideos.length;
      const total = snapshot.sceneCount ? `/${snapshot.sceneCount}` : '';
      messages.push(`分镜视频已生成 ${snapshot.sceneVideos.length}${total} 条`);
    }
    if (snapshot.finalVideoPath && !lastMilestones.final) {
      lastMilestones.final = true;
      messages.push('最终成片已生成，正在整理交付信息');
    }

    if (messages.length === 0) {
      const summary = buildProgressText(snapshot);
      if (summary) messages.push(summary);
    }

    for (const msg of messages) {
      context.sendProgressUpdate(msg);
    }
  };

  emitSnapshot();
  const timer = setInterval(emitSnapshot, 5000);
  if (typeof timer.unref === 'function') timer.unref();

  return {
    stop() {
      clearInterval(timer);
      emitSnapshot();
    },
  };
}

function buildSafeEnv(context) {
  const pythonBin = context.env.get('PYTHON_BIN')
    || process.env.PYTHON_BIN
    || 'python3.12';

  const env = {
    PATH: process.env.PATH || '',
    HOME: process.env.HOME || '',
    PYTHONPATH: LIB_DIR,
  };

  const dotenvPath = context.env.get('DOTENV_PATH')
    || process.env.DOTENV_PATH
    || join(REPO_ROOT, '.env');
  if (dotenvPath) {
    env.DOTENV_PATH = dotenvPath;
  }

  const resourcesPath = context.env.get('VIDEO_RESOURCES_PATH')
    || process.env.VIDEO_RESOURCES_PATH
    || join(LIB_DIR, 'video_resources');
  if (resourcesPath) {
    env.VIDEO_RESOURCES_PATH = resourcesPath;
  }

  env.OPENCLAW_OUTPUT_DIR = context.env.get('OPENCLAW_OUTPUT_DIR')
    || process.env.OPENCLAW_OUTPUT_DIR
    || DEFAULT_OUTPUT_DIR;

  for (const key of ALLOWED_ENV_KEYS) {
    const value = context.env.get(key);
    if (value) {
      env[key] = value;
    }
  }

  return { env, pythonBin };
}

/**
 * 执行 Python 脚本
 * FIX #7: cwd 设为 SKILL_DIR 而非 LIB_DIR，避免污染 lib/ 目录
 */
function runPythonScript(scriptName, args, context) {
  const scriptPath = join(SCRIPTS_DIR, scriptName);
  const { env: safeEnv, pythonBin } = buildSafeEnv(context);

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonBin, [scriptPath, ...args], {
      cwd: SKILL_DIR,
      env: safeEnv,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      if (context.sendProgressUpdate) {
        context.sendProgressUpdate(text.trim());
      }
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(new Error(
          `脚本执行失败（exit code ${code}）:\n${stderr || stdout}`
        ));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`无法启动 Python 进程: ${err.message}`));
    });
  });
}

/**
 * 解析脚本输出
 * FIX #6: 脚本输出 JSON，优先按 JSON 解析，降级到正则
 */
function parseOutput(stdout) {
  // 尝试从 stdout 中提取最后一个完整的 JSON 对象
  // 脚本可能在 JSON 之前输出日志，所以从后往前找
  const lines = stdout.trim().split('\n');
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (line.startsWith('{')) {
      // 可能是 JSON 的开头，尝试向下拼接直到找到完整 JSON
      const jsonCandidate = lines.slice(i).join('\n');
      try {
        const data = JSON.parse(jsonCandidate);
        return {
          video_path: data.final_video || data.final_video_path || data.output_path || data.video_path || null,
          workspace_dir: data.workspace_dir || data.output_dir || null,
          duration: data.duration || data.total_duration || null,
          scene_count: data.scene_count || data.total_scenes
            || (data.generation_summary && data.generation_summary.total_scenes) || null,
          engine_used: data.video_engine || data.engine
            || (data.generation_summary && data.generation_summary.video_engine) || null,
        };
      } catch {
        // 不是有效 JSON，继续找
      }
    }
  }

  // JSON 解析失败，降级到正则（兼容可能的文本输出）
  const result = {
    video_path: null,
    workspace_dir: null,
    duration: null,
    scene_count: null,
    engine_used: null,
  };

  const videoMatch = stdout.match(/最终视频[：:]\s*(.+\.mp4)/m)
    || stdout.match(/final.*?:\s*(.+\.mp4)/im)
    || stdout.match(/"(?:final_video_path|output_path)":\s*"(.+\.mp4)"/m);
  if (videoMatch) result.video_path = videoMatch[1].trim();

  const wsMatch = stdout.match(/"workspace_dir":\s*"(.+?)"/m)
    || stdout.match(/workspace[：:]\s*(.+)/im);
  if (wsMatch) result.workspace_dir = wsMatch[1].trim();

  return result;
}

/**
 * 创建标准化 workspace 目录
 */
async function createWorkspace(workflow, context) {
  try {
    const args = ['create', '--workflow', workflow];
    const outputDir = context.env.get('OPENCLAW_OUTPUT_DIR');
    if (outputDir) args.push('--output_base_dir', outputDir);

    const { stdout } = await runPythonScript('workspace_manager.py', args, context);
    return JSON.parse(stdout.trim());
  } catch (err) {
    context.log.info(`Workspace 创建失败，使用默认路径: ${err.message}`);
    return null;
  }
}

/**
 * OpenClaw Plugin 注册入口
 */
const plugin = {
  id: 'capsule-cinema',
  name: 'Video Agent',
  description: 'AI 视频创作全流程代理',
  configSchema: { type: 'object', additionalProperties: false, properties: {} },
  register(api) {
    // skill-only plugin, no channel registration needed
  },
};

export default plugin;

/**
 * OpenClaw Skill 主执行函数
 *
 * @param {Object} inputs - 来自 skill.md 定义的输入参数
 * @param {import('@openclaw/skill-sdk').SkillContext} context - OpenClaw 执行上下文
 * @returns {Promise<Object>} 符合 skill.md outputs 定义的返回对象
 */
export async function execute(inputs, context) {
  context.setLongRunning(true);

  // FIX #2: 验证实际存在的环境变量名
  const geminiKey = context.env.get('GEMINI3_API_KEY')
    || context.env.get('GEMINI3_PRO_API_KEY')
    || context.env.get('GEMEINI_IMAGE_MODEL_API_KEY');
  if (!geminiKey) {
    throw new Error(
      '缺少 Gemini API 密钥，请在 OpenClaw 设定中配置 GEMINI3_API_KEY 或 GEMINI3_PRO_API_KEY。'
    );
  }

  const crewKey = context.env.get('CREW_API_KEY');
  if (!crewKey) {
    throw new Error('缺少必要环境变量 CREW_API_KEY，请在 OpenClaw 设定中配置。');
  }

  const workflow = inferWorkflow(inputs);
  const route = WORKFLOW_ROUTES[workflow];

  if (!route) {
    throw new Error(
      `未知的工作流类型: ${workflow}。支持: ${Object.keys(WORKFLOW_ROUTES).join(', ')}`
    );
  }

  context.log.info(`执行工作流: ${route.workflow} (${workflow})`);
  context.sendProgressUpdate(`正在执行工作流 ${route.workflow}: ${workflow}...`);

  // 输入前置校验：确保脚本 required 参数已提供，避免晦涩的 argparse 报错
  if (workflow === 'feedback' && !inputs.scene_id) {
    throw new Error(
      '反馈工作流（工作流 D）需要指定 scene_id（要重生成的分镜编号）。'
    );
  }
  if (!route.script) {
    throw new Error(`工作流 ${workflow} 不支持自动执行。`);
  }

  // 创建统一 workspace
  const workspace = await createWorkspace(workflow, context);
  if (workspace) {
    context.log.info(`Workspace: ${workspace.workspace_dir}`);
    context.sendProgressUpdate(`工作目录已创建：${workspace.workspace_dir}`);
  }

  // FIX #5: buildArgs 按脚本名过滤参数，只传递实际支持的
  const args = buildArgs(route.script, inputs);

  // FIX #1: 只有脚本实际支持 --output_dir 时才传递
  if (workspace && route.supports_output_dir && !inputs.workspace_dir) {
    args.push('--output_dir', workspace.workspace_dir);
  }

  // storyboard-only 工作流：只生成分镜，不执行视频生成
  if (route.storyboard_only) {
    args.push('--storyboard_only');
  }

  const monitor = startWorkspaceMonitor(workspace?.workspace_dir || null, context);
  let stdout = '';
  try {
    ({ stdout } = await runPythonScript(route.script, args, context));
  } finally {
    monitor.stop();
  }
  const result = parseOutput(stdout);

  // 如果脚本没有返回 workspace_dir，用我们创建的
  if (!result.workspace_dir && workspace) {
    result.workspace_dir = workspace.workspace_dir;
  }

  const artifacts = collectWorkspaceArtifacts(result.workspace_dir || workspace?.workspace_dir || null);
  if (artifacts.storyboardPath) {
    context.sendProgressUpdate(buildProgressText(artifacts) || '已整理出中间产物');
  }

  if (!result.video_path && artifacts.finalVideoPath) {
    result.video_path = artifacts.finalVideoPath;
  }

  context.log.info(`工作流 ${route.workflow} 执行完成`);
  if (result.video_path) {
    context.log.info(`视频路径: ${result.video_path}`);
  }

  // 格式化分镜信息供用户查看
  let formattedStoryboard = null;
  if ((!result.storyboard || !Array.isArray(result.storyboard)) && artifacts.storyboardPreview.length > 0) {
    formattedStoryboard = artifacts.storyboardPreview;
  }
  if (result.storyboard && Array.isArray(result.storyboard)) {
    formattedStoryboard = result.storyboard.map((scene, idx) => {
      const sceneInfo = {
        scene_id: scene.scene_id ?? idx,
        description: scene.description || '无描述',
        duration: scene.duration || 0,
      };

      // 添加图片相关信息
      if (scene.image_prompt_chinese) {
        sceneInfo.image_prompt_chinese = scene.image_prompt_chinese;
      }
      if (scene.image_prompt_english) {
        sceneInfo.image_prompt_english = scene.image_prompt_english;
      }
      if (scene.image_path) {
        sceneInfo.image_path = scene.image_path;
      }

      // 添加视频相关信息
      if (scene.video_prompt_chinese) {
        sceneInfo.video_prompt_chinese = scene.video_prompt_chinese;
      }
      if (scene.video_prompt_english) {
        sceneInfo.video_prompt_english = scene.video_prompt_english;
      }
      if (scene.video_path) {
        sceneInfo.video_path = scene.video_path;
      }

      // 添加配音和字幕
      if (scene.narration) {
        sceneInfo.narration = scene.narration;
      }
      if (scene.subtitle) {
        sceneInfo.subtitle = scene.subtitle;
      }

      return sceneInfo;
    });
  }

  const previewImages = artifacts.previewImages.slice(0, 3);
  const referenceImages = artifacts.referenceImages.slice(0, 4);
  const sceneVideoPaths = artifacts.sceneVideos.slice(0, 5);
  const coverImage = result.cover_image || previewImages[0] || referenceImages[0] || null;
  const progressSummary = buildProgressText(artifacts);

  return {
    video_path: result.video_path,
    video_url: null,
    workspace_dir: result.workspace_dir,
    storyboard: result.storyboard || null,
    storyboard_formatted: formattedStoryboard,
    storyboard_path: result.storyboard_path || artifacts.storyboardPath || null,
    cover_image: coverImage,
    preview_images: previewImages,
    reference_images: referenceImages,
    scene_video_paths: sceneVideoPaths,
    progress_summary: progressSummary || null,
    video_title: result.video_title || null,
    social_media_copywriting: result.social_media_copywriting || null,
    duration: result.duration,
    scene_count: result.scene_count || artifacts.sceneCount,
    engine_used: result.engine_used || inputs.video_engine || 'jimeng35pro',
    generation_summary: result.generation_summary || null,
  };
}
