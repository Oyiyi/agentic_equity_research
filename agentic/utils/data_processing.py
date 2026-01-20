import json
import re


def robust_load_json(text):
    """
    Robustly load JSON from text that may contain markdown code blocks or extra text.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If no valid JSON object found
    """
    def extract_outer_braces(text):
        stack = []
        start = None

        for i, char in enumerate(text):
            if char == '{':
                if start is None:
                    start = i
                stack.append(char)
            elif char == '}':
                stack.pop()
                if not stack:
                    return text[start:i + 1]
        return None
    
    try:
        response_json = json.loads(text[7:-3].strip())
        return response_json
    except Exception as e:
        try:
            response_json = json.loads(text)
            return response_json
        except Exception as e:
            pass
        
    try:
        response_json = json.loads(text[8:-3].strip())
        return response_json
    except Exception as e:
        pass
    
    try:
        response_json = extract_outer_braces(text)
        return json.loads(response_json)
    except Exception as e:
        pass
    
    try:
        json_pattern = re.compile(r'```json\n(.*?)\n```', re.DOTALL)
        matches = json_pattern.search(text)
        if matches:
            try:
                return json.loads(matches.group(1))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        pass
    
    try:
        json_pattern = r'\{(?:[^{}]|(?R))*\}'
        matches = re.findall(json_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        raise ValueError("No valid JSON object found")
    
    except Exception as e:
        raise ValueError("No valid JSON object found")
