# convert_js_to_json.py
import json
import sys
import re

def js_to_json(js_content):
    # コメントを削除
    js_content = re.sub(r'//.*?$', '', js_content, flags=re.MULTILINE)
    
    # 'const sampleCompanyData =' 部分を削除
    js_content = re.sub(r'const\s+\w+\s*=\s*', '', js_content)
    
    # 末尾のセミコロンを削除
    js_content = js_content.strip().rstrip(';')
    
    # プロパティ名の引用符処理
    js_content = re.sub(r'(\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', js_content)
    
    # 文字列として返す
    return js_content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用法: python convert_js_to_json.py input.js [output.json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.js', '.json')
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        json_content = js_to_json(js_content)
        
        # JSONとして解析して整形
        parsed_json = json.loads(json_content)
        formatted_json = json.dumps(parsed_json, ensure_ascii=False, indent=2)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_json)
        
        print(f"変換完了: {output_file}")
    
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)