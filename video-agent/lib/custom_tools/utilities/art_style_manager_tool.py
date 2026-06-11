from typing import Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import yaml
import os
from pathlib import Path
from src.logger import get_logger

# 初始化日志记录器
logger = get_logger("art_style_manager")

class ArtStyleManagerToolSchema(BaseModel):
    """Input for ArtStyleManagerTool."""
    action: str = Field(
        description="操作类型：'list' 列出所有可用风格，'get' 获取指定风格详情，'create' 创建新风格"
    )
    style_code: str = Field(
        default="",
        description="风格代码（用于get和create操作）"
    )
    style_config: dict = Field(
        default_factory=dict,
        description="新风格配置（仅用于create操作），必须包含：style_name（风格名称），style_description（风格描述），visual_style（结构化的视觉风格配置，包含颜色、排版、构图、特效四个部分）"
    )

class ArtStyleManagerTool(BaseTool):
    name: str = "Manage art styles - list, get or create art style configurations"
    description: str = (
        "A tool that manages art style configurations in the art_styles directory. "
        "Available actions:\n"
        "- 'list': List all available art styles with their names and codes\n"
        "- 'get': Get detailed configuration of a specific art style by style_code\n"
        "- 'create': Create a new art style YAML file with provided configuration\n"
        "Use this tool to check if an existing art style matches user requirements, "
        "or create a new one if needed."
    )
    args_schema: Type[BaseModel] = ArtStyleManagerToolSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化ArtStyleManagerTool")

    def _get_art_styles_dir(self) -> Path:
        """获取art_styles目录路径"""
        # __file__ -> custom_tools/utilities/art_style_manager_tool.py
        # dirname -> custom_tools/utilities
        # dirname -> custom_tools
        # dirname -> video-agent/lib
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        art_styles_dir = Path(project_root) / 'art_styles'

        # 确保目录存在
        art_styles_dir.mkdir(parents=True, exist_ok=True)

        return art_styles_dir

    def _run(self, action: str = 'list', style_code: str = "", style_config: dict = None) -> Any:
        """管理艺术风格配置

        Args:
            action: 操作类型 ('list', 'get', 'create')
            style_code: 风格代码
            style_config: 新风格配置（仅用于create）
        """
        try:
            if action == 'list':
                return self._list_styles()
            elif action == 'get':
                if not style_code:
                    return {
                        "error": "获取风格详情需要提供style_code参数",
                        "success": False
                    }
                return self._get_style(style_code)
            elif action == 'create':
                if not style_code or not style_config:
                    return {
                        "error": "创建新风格需要提供style_code和style_config参数",
                        "success": False
                    }
                return self._create_style(style_code, style_config)
            else:
                logger.error(f"不支持的操作类型: {action}")
                return {
                    "error": f"不支持的操作类型: {action}，请使用 'list'、'get' 或 'create'",
                    "success": False
                }

        except Exception as e:
            logger.error(f"艺术风格管理操作失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "error": f"操作失败: {str(e)}",
                "success": False
            }

    def _list_styles(self) -> dict:
        """列出所有可用的艺术风格（包括永久风格和临时风格）"""
        art_styles_dir = self._get_art_styles_dir()
        tmp_styles_dir = art_styles_dir / 'tmp'

        logger.info(f"列出艺术风格目录中的所有风格: {art_styles_dir}")

        # 查找永久风格目录中的yaml文件
        yaml_files = list(art_styles_dir.glob("*.yaml"))

        # 查找临时风格目录中的yaml文件
        tmp_yaml_files = []
        if tmp_styles_dir.exists():
            tmp_yaml_files = list(tmp_styles_dir.glob("*.yaml"))
            logger.info(f"找到 {len(tmp_yaml_files)} 个临时风格")

        all_yaml_files = yaml_files + tmp_yaml_files

        if not all_yaml_files:
            logger.warning("未找到任何艺术风格配置文件")
            return {
                "success": True,
                "total_count": 0,
                "permanent_count": 0,
                "temporary_count": 0,
                "styles": [],
                "message": "未找到任何艺术风格配置文件"
            }

        styles_list = []
        for yaml_file in all_yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    style_data = yaml.safe_load(f)

                if style_data:
                    # 判断是否是临时风格
                    is_temporary = yaml_file.parent.name == 'tmp'

                    style_info = {
                        "style_name": style_data.get('style_name', ''),
                        "style_code": style_data.get('style_code', yaml_file.stem),
                        "file_name": yaml_file.name,
                        "is_temporary": is_temporary,
                        "style_description_preview": style_data.get('style_description', '')[:100] + "..." if len(style_data.get('style_description', '')) > 100 else style_data.get('style_description', '')
                    }

                    if is_temporary:
                        style_info["note"] = "临时风格（仅本次有效）"

                    styles_list.append(style_info)
            except Exception as e:
                logger.warning(f"读取风格文件 {yaml_file.name} 失败: {str(e)}")
                continue

        # 统计数量
        permanent_count = len([s for s in styles_list if not s.get('is_temporary', False)])
        temporary_count = len([s for s in styles_list if s.get('is_temporary', False)])

        result = {
            "success": True,
            "total_count": len(styles_list),
            "permanent_count": permanent_count,
            "temporary_count": temporary_count,
            "styles": styles_list,
            "art_styles_dir": str(art_styles_dir),
            "tmp_styles_dir": str(tmp_styles_dir)
        }

        logger.info(f"成功列出 {len(styles_list)} 个艺术风格（永久: {permanent_count}, 临时: {temporary_count}）")
        return result

    def _get_style(self, style_code: str) -> dict:
        """获取指定风格的详细配置（优先从永久目录查找，其次从临时目录查找）"""
        art_styles_dir = self._get_art_styles_dir()
        tmp_styles_dir = art_styles_dir / 'tmp'

        # 优先查找永久风格
        style_file = art_styles_dir / f"{style_code}.yaml"
        is_temporary = False

        # 如果永久目录不存在，查找临时目录
        if not style_file.exists() and tmp_styles_dir.exists():
            tmp_style_file = tmp_styles_dir / f"{style_code}.yaml"
            if tmp_style_file.exists():
                style_file = tmp_style_file
                is_temporary = True

        logger.info(f"获取艺术风格详情: {style_code} ({'临时' if is_temporary else '永久'})")

        if not style_file.exists():
            logger.error(f"艺术风格文件不存在: {style_file}")
            return {
                "error": f"艺术风格 '{style_code}' 不存在（已在永久和临时目录中查找）",
                "style_code": style_code,
                "file_path": str(style_file),
                "success": False
            }

        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                style_data = yaml.safe_load(f)

            if not style_data:
                logger.error(f"艺术风格文件为空: {style_file}")
                return {
                    "error": f"艺术风格文件为空",
                    "style_code": style_code,
                    "success": False
                }

            result = {
                "success": True,
                "style_code": style_code,
                "style_name": style_data.get('style_name', ''),
                "style_description": style_data.get('style_description', ''),
                "visual_style": style_data.get('visual_style', {}),
                "is_temporary": is_temporary,
                # 保留旧格式字段以兼容
                "image_style_keywords": style_data.get('image_style_keywords', ''),
                "video_style_description": style_data.get('video_style_description', ''),
                "video_style_keywords": style_data.get('video_style_keywords', ''),
                "file_path": str(style_file)
            }

            if is_temporary:
                result["note"] = "临时风格（仅本次有效），如需永久使用请将文件移动到上级目录"

            logger.info(f"成功获取艺术风格 '{style_code}' 的配置")
            return result

        except Exception as e:
            logger.error(f"读取艺术风格文件失败: {str(e)}")
            return {
                "error": f"读取风格文件失败: {str(e)}",
                "style_code": style_code,
                "success": False
            }

    def _create_style(self, style_code: str, style_config: dict) -> dict:
        """创建新的艺术风格配置文件"""
        art_styles_dir = self._get_art_styles_dir()
        style_file = art_styles_dir / f"{style_code}.yaml"

        logger.info(f"创建新艺术风格: {style_code}")

        # 检查文件是否已存在
        if style_file.exists():
            logger.warning(f"艺术风格 '{style_code}' 已存在，将覆盖")

        # 验证必需字段
        required_fields = ['style_name', 'style_description']
        missing_fields = [field for field in required_fields if field not in style_config]

        if missing_fields:
            logger.error(f"缺少必需字段: {missing_fields}")
            return {
                "error": f"缺少必需字段: {', '.join(missing_fields)}。必需字段：style_name（风格名称）, style_description（风格描述）, visual_style（视觉风格配置）",
                "required_fields": required_fields,
                "success": False
            }

        # 检查是否提供了visual_style（新格式）
        if 'visual_style' not in style_config:
            logger.error("缺少visual_style字段")
            return {
                "error": "缺少必需字段：visual_style（结构化的视觉风格配置）。visual_style必须包含：颜色、排版、构图、特效四个部分",
                "required_fields": required_fields + ['visual_style'],
                "success": False
            }

        try:
            # 构建完整的YAML配置（新格式）
            yaml_content = {
                "style_name": style_config['style_name'],
                "style_code": style_code,
                "style_description": style_config['style_description'],
                "visual_style": style_config['visual_style']
            }

            # 写入YAML文件
            with open(style_file, 'w', encoding='utf-8') as f:
                # 添加注释
                f.write(f"# {style_config['style_name']}风格配置\n")
                f.write(f"style_name: \"{style_config['style_name']}\"\n")
                f.write(f"style_code: \"{style_code}\"\n")
                f.write(f"style_description: \"{style_config['style_description']}\"\n")
                f.write("\n# 视频视觉风格 - 结构化配置（用于图生视频，控制视觉风格）\n")
                f.write("visual_style:\n")

                # 写入visual_style的结构化内容
                visual_style = style_config['visual_style']

                # 写入颜色配置
                if '颜色' in visual_style:
                    f.write("  颜色:\n")
                    color_config = visual_style['颜色']
                    if '主色调' in color_config:
                        f.write("    主色调: ")
                        f.write(yaml.dump(color_config['主色调'], allow_unicode=True, default_flow_style=True).strip())
                        f.write("\n")
                    if '辅助色' in color_config:
                        f.write("    辅助色: ")
                        f.write(yaml.dump(color_config['辅助色'], allow_unicode=True, default_flow_style=True).strip())
                        f.write("\n")
                    if '氛围特征' in color_config:
                        f.write(f"    氛围特征: \"{color_config['氛围特征']}\"\n")

                # 写入排版配置
                if '排版' in visual_style:
                    f.write("  排版:\n")
                    layout_config = visual_style['排版']
                    if '元素布局' in layout_config:
                        f.write(f"    元素布局: \"{layout_config['元素布局']}\"\n")
                    if '层次关系' in layout_config:
                        f.write(f"    层次关系: \"{layout_config['层次关系']}\"\n")

                # 写入构图配置
                if '构图' in visual_style:
                    f.write("  构图:\n")
                    composition_config = visual_style['构图']
                    if '类型' in composition_config:
                        f.write(f"    类型: \"{composition_config['类型']}\"\n")
                    if '特征' in composition_config:
                        f.write(f"    特征: \"{composition_config['特征']}\"\n")
                    if '视角' in composition_config:
                        f.write(f"    视角: \"{composition_config['视角']}\"\n")

                # 写入特效配置
                if '特效' in visual_style:
                    f.write("  特效:\n")
                    effects_config = visual_style['特效']
                    if '元素' in effects_config:
                        f.write("    元素:\n")
                        for element in effects_config['元素']:
                            f.write(f"      - \"{element}\"\n")
                    if '质感' in effects_config:
                        f.write(f"    质感: \"{effects_config['质感']}\"\n")

            result = {
                "success": True,
                "style_code": style_code,
                "style_name": style_config['style_name'],
                "file_path": str(style_file),
                "message": f"成功创建艺术风格 '{style_config['style_name']}'"
            }

            logger.info(f"✅ 成功创建艺术风格文件: {style_file}")
            return result

        except Exception as e:
            logger.error(f"创建艺术风格文件失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "error": f"创建风格文件失败: {str(e)}",
                "style_code": style_code,
                "success": False
            }
