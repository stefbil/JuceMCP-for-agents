# JuceMCP-for-agents

Create python environment.

```cmd
pip install -r requirements.txt
```
Paste the following to the agent:
Remember to replace command and args with the full directory leading to the python.exe and juce_mcp.py files.

```json
{
  "mcpServers": {
    "juce-docs": {
      "command": "./jucemcp_env/Scripts/python.exe",
      "args": [
        "./juceMCP/juce_mcp.py"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```
