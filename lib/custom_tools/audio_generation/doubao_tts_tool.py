#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包TTS语音合成CrewAI工具
使用豆包TTS API进行文字转语音合成
"""

import os
import json
import uuid
import base64
import requests
from typing import Type, Optional
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field

from .base_tool_compat import BaseTool

# 加载环境变量
load_dotenv()


def _redact_secret(value: Optional[str]) -> str:
    if not value:
        return "<unset>"
    return "<set>"


class DoubaoTTSSchema(BaseModel):
    """豆包TTS工具的输入参数"""
    text: str = Field(
        ..., 
        description="要转换为语音的文本内容"
    )
    output_path: str = Field(
        default=None,
        description="输出音频文件的保存路径，如果不指定则自动生成"
    )
    voice_type: str = Field(
        default="science_female",
        description="音色类型，可选：science_female, science_male, male_default, female_default等"
    )
    speed_ratio: float = Field(
        default=1.2,
        description="语速比例，范围[0.8, 2.0]，1.0为正常语速"
    )
    encoding: str = Field(
        default="mp3",
        description="音频编码格式：wav, pcm, ogg_opus, mp3"
    )


class DoubaoTTSTool(BaseTool):
    name: str = "豆包TTS语音合成工具"
    description: str = (
        "使用豆包TTS API将文字转换为语音的工具。支持多种音色和语音参数调节。"
        "可以生成高质量的中文语音，适合科普解说、播报等场景。"
    )
    args_schema: Type[BaseModel] = DoubaoTTSSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def _run(
        self,
        text: str,
        output_path: str = None,
        voice_type: str = "science_female",
        speed_ratio: float = 1.2,
        encoding: str = "mp3"
    ) -> str:
        """
        执行豆包TTS语音合成
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            voice_type: 音色类型
            speed_ratio: 语速比例
            encoding: 音频格式
            
        Returns:
            生成结果的描述信息
        """
        try:
            # 初始化豆包TTS客户端
            client = DoubaoTTSClient(voice_type=voice_type)
            
            # 合成语音
            result_path = client.synthesize_speech(
                text=text,
                output_path=output_path,
                encoding=encoding,
                speed_ratio=speed_ratio
            )
            
            if result_path:
                return f"✅ 豆包TTS语音合成成功！音频已保存到: {result_path}"
            else:
                return "❌ 豆包TTS语音合成失败"
            
        except Exception as e:
            return f"❌ 豆包TTS语音合成失败: {str(e)}"


class DoubaoTTSClient:
    """豆包TTS客户端"""
    
    # 预设音色配置
    VOICE_PRESETS = {
        # 男声
        'male_default': 'zh_male_xuefeng_mars_bigtts',
        'male_sunwukong': 'zh_male_sunwukong_mars_bigtts',
        'male_narrator': 'zh_male_narrator_mars_bigtts',
        'male_warm': 'zh_male_warm_mars_bigtts',
        
        # 女声
        'female_default': 'zh_female_peiqi_mars_bigtts',
        'female_gentle': 'zh_female_gentle_mars_bigtts',
        'female_sweet': 'zh_female_sweet_mars_bigtts',
        'female_narrator': 'zh_female_narrator_mars_bigtts',
        
        # 科普专用推荐音色
        'science_male': 'zh_male_xuefeng_mars_bigtts',
        'science_female': 'zh_female_peiqi_mars_bigtts'
    }
    
    def __init__(self, voice_type: str = 'science_female'):
        """初始化豆包TTS客户端"""
        # 获取环境变量
        self.appid = os.getenv('DOUBAO_TTS_APPID')
        self.access_token = os.getenv('DOUBAO_TTS_ACCESS_TOKEN')
        self.secret_key = os.getenv('DOUBAO_TTS_SECRET_KEY')
        self.cluster_id = os.getenv('DOUBAO_TTS_CLUSTER_ID', 'volcano_tts')
        
        # API配置
        self.api_url = "https://openspeech.bytedance.com/api/v1/tts"
        
        # 设置音色
        self.voice_type = self._resolve_voice_type(voice_type)
        
        # 验证环境变量
        self._validate_environment()

    def _validate_environment(self):
        """验证环境变量配置"""
        missing_vars = []
        
        if not self.appid:
            missing_vars.append('DOUBAO_TTS_APPID')
        if not self.access_token:
            missing_vars.append('DOUBAO_TTS_ACCESS_TOKEN')
        
        if missing_vars:
            error_msg = f"缺少必需的环境变量: {', '.join(missing_vars)}"
            raise ValueError(error_msg)

    def _resolve_voice_type(self, voice_type: str) -> str:
        """解析音色类型"""
        if voice_type in self.VOICE_PRESETS:
            return self.VOICE_PRESETS[voice_type]
        else:
            return voice_type

    def synthesize_speech(self, text: str, output_path: Optional[str] = None, 
                         encoding: str = "mp3", speed_ratio: float = 1.2,
                         voice_override: Optional[str] = None) -> Optional[str]:
        """合成语音"""
        try:
            # 参数验证
            if not text or not text.strip():
                print("❌ 文本内容为空")
                return None
            
            if not (0.8 <= speed_ratio <= 2.0):
                print(f"⚠️ 语速比例 {speed_ratio} 超出范围 [0.8, 2.0]，将调整到范围内")
                speed_ratio = max(0.8, min(2.0, speed_ratio))
            
            # 确定使用的音色
            current_voice = voice_override if voice_override else self.voice_type
            if voice_override and voice_override in self.VOICE_PRESETS:
                current_voice = self.VOICE_PRESETS[voice_override]
            
            # 生成请求ID
            req_id = str(uuid.uuid4())
            
            # 构建请求参数
            payload = {
                "app": {
                    "appid": self.appid,
                    "token": self.access_token,
                    "cluster": self.cluster_id
                },
                "user": {
                    "uid": "user_" + req_id[:8]
                },
                "audio": {
                    "voice_type": current_voice,
                    "encoding": encoding,
                    "speed_ratio": speed_ratio,
                    "rate": 24000,
                    "bitrate": 160
                },
                "request": {
                    "reqid": req_id,
                    "text": text,
                    "operation": "query"
                }
            }
            
            # 设置请求头
            headers = {
                "Authorization": f"Bearer;{self.access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"🎙️ 开始语音合成...")
            print(f"   📝 文本长度: {len(text)} 字符")
            print(f"   🎵 音色: {current_voice}")
            print(f"   ⚡ 语速: {speed_ratio}x")
            print(f"   🔊 格式: {encoding}")
            print(f"   🔑 APPID: {_redact_secret(self.appid)}")
            print(f"   🔑 Token: {_redact_secret(self.access_token)}")

            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=60
            )

            # 检查响应状态
            if response.status_code != 200:
                print(f"❌ HTTP错误 {response.status_code}")
                print(f"   响应内容: {response.text[:500]}")
                print(f"   请求URL: {self.api_url}")
                print(
                    "   请求摘要: "
                    f"voice_type={current_voice}, encoding={encoding}, "
                    f"speed_ratio={speed_ratio}, text_len={len(text)}, reqid={req_id}"
                )
                response.raise_for_status()

            # 解析响应
            result = response.json()
            response_summary = {
                key: value
                for key, value in result.items()
                if key not in {"data"}
            }
            if "data" in result:
                response_summary["data"] = "<audio_base64>"
            print(f"   📋 响应摘要: {json.dumps(response_summary, ensure_ascii=False)[:500]}")
            
            if result.get("code") == 3000:
                # 成功获取音频数据
                audio_data = base64.b64decode(result["data"])
                duration = result.get("addition", {}).get("duration", 0)
                
                # 生成输出文件路径
                if not output_path:
                    timestamp = req_id[:8]
                    output_path = f"tts_output_{timestamp}.{encoding}"
                
                # 确保输出目录存在
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 保存音频文件
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                
                # 计算实际时长（毫秒转秒）
                try:
                    duration_num = int(duration) if duration else 0
                    duration_seconds = duration_num / 1000 if duration_num > 0 else 0
                except (ValueError, TypeError):
                    duration_seconds = 0
                
                print(f"✅ 语音合成成功!")
                print(f"   📁 文件路径: {output_file.absolute()}")
                print(f"   ⏱️ 音频时长: {duration_seconds:.2f}秒")
                print(f"   📊 文件大小: {len(audio_data) / 1024:.1f} KB")
                
                return str(output_file.absolute())
                
            else:
                error_msg = result.get("message", "未知错误")
                error_code = result.get("code", "未知")
                print(f"❌ API错误 (代码: {error_code}): {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            print("❌ 请求超时，请检查网络连接")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求错误: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ 响应解析错误: {str(e)}")
            return None
        except Exception as e:
            print(f"❌ 语音合成失败: {str(e)}")
            return None

    def batch_synthesize(self, text_list: list, output_dir: str, 
                        filename_template: str = "audio_{:02d}.mp3",
                        **kwargs) -> list:
        """批量合成语音"""
        output_files = []
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"🎙️ 开始批量语音合成: {len(text_list)} 个文本")
        
        for i, text in enumerate(text_list):
            try:
                filename = filename_template.format(i)
                output_file = output_path / filename
                
                print(f"   📝 处理第 {i+1}/{len(text_list)} 个文本...")
                
                result = self.synthesize_speech(
                    text=text,
                    output_path=str(output_file),
                    **kwargs
                )
                
                if result:
                    output_files.append(result)
                else:
                    print(f"⚠️ 第 {i+1} 个文本合成失败")
                    output_files.append(None)
                
                # 添加延迟避免API限制
                if i < len(text_list) - 1:
                    import time
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ 第 {i+1} 个文本处理异常: {str(e)}")
                output_files.append(None)
        
        successful_count = len([f for f in output_files if f is not None])
        print(f"✅ 批量合成完成: {successful_count}/{len(text_list)} 成功")
        
        return output_files

    def get_voice_info(self):
        """获取当前音色信息"""
        return {
            'current_voice': self.voice_type,
            'available_presets': list(self.VOICE_PRESETS.keys()),
            'api_url': self.api_url,
            'cluster_id': self.cluster_id
        }

    def set_voice(self, voice_type: str):
        """设置音色"""
        self.voice_type = self._resolve_voice_type(voice_type)
        print(f"🎵 音色已切换为: {self.voice_type}")

    @classmethod
    def list_voice_presets(cls):
        """列出所有预设音色"""
        return cls.VOICE_PRESETS.copy()

    @classmethod
    def validate_config(cls):
        """验证配置"""
        checks = {}
        
        # 检查环境变量
        required_vars = ['DOUBAO_TTS_APPID', 'DOUBAO_TTS_ACCESS_TOKEN']
        for var in required_vars:
            checks[f'env_{var}'] = bool(os.getenv(var))
        
        # 可选环境变量
        optional_vars = ['DOUBAO_TTS_SECRET_KEY', 'DOUBAO_TTS_CLUSTER_ID']
        for var in optional_vars:
            checks[f'env_{var}'] = bool(os.getenv(var))
        
        return checks 
