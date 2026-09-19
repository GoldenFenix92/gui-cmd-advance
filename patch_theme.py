import json
import os
import customtkinter

theme_path = os.path.join(os.path.dirname(customtkinter.__file__), "assets", "themes", "blue.json")
with open(theme_path, "r") as f:
    theme = json.load(f)

# Override specific colors with GitHub palette
theme["CTk"]["fg_color"] = ["#F6F8FA", "#0D1117"]
theme["CTkToplevel"]["fg_color"] = ["#F6F8FA", "#0D1117"]
theme["CTkFrame"]["fg_color"] = ["#FFFFFF", "#161B22"]
theme["CTkFrame"]["top_fg_color"] = ["#FFFFFF", "#161B22"]
theme["CTkFrame"]["border_color"] = ["#D0D7DE", "#30363D"]
theme["CTkButton"]["fg_color"] = ["#1F883D", "#238636"]
theme["CTkButton"]["hover_color"] = ["#1A7F37", "#2EA043"]
theme["CTkButton"]["text_color"] = ["#FFFFFF", "#FFFFFF"]
theme["CTkLabel"]["text_color"] = ["#24292F", "#C9D1D9"]
theme["CTkTextbox"]["fg_color"] = ["#F6F8FA", "#0D1117"]
theme["CTkTextbox"]["text_color"] = ["#24292F", "#C9D1D9"]
theme["CTkCheckBox"]["fg_color"] = ["#0969DA", "#2F81F7"]
theme["CTkCheckBox"]["hover_color"] = ["#0969DA", "#2F81F7"]
theme["CTkSwitch"]["progress_color"] = ["#1F883D", "#238636"]
theme["CTkOptionMenu"]["fg_color"] = ["#F6F8FA", "#21262D"]
theme["CTkOptionMenu"]["button_color"] = ["#F6F8FA", "#21262D"]
theme["CTkOptionMenu"]["button_hover_color"] = ["#F3F4F6", "#30363D"]
theme["CTkScrollableFrame"]["label_fg_color"] = ["#FFFFFF", "#161B22"]

out_path = r"C:\Users\lsc_e\.gemini\antigravity-ide\scratch\custom_github_theme.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(theme, f, indent=2)
