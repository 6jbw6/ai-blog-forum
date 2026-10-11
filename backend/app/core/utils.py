"""头像统一策略：未上传即展示空白占位（前端 /user-avatar.svg）。

历史版本会按邮箱 / 用户名生成 Gravatar / dicebear 兜底头像，
现一律不再生成——avatar 字段原样返回，None 即空白。
"""
