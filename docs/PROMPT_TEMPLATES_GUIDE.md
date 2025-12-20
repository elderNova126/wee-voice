# 🎯 Prompt Templates - Quick Reference

## 📂 Location
All prompt templates are stored in: **`backend/app/prompts/`**

## 📝 Available Templates

### Conversation Style
- **`conversation_style_fr.txt`** - French conversation rules
- **`conversation_style_en.txt`** - English conversation rules

**Contains:**
- Natural conversation guidelines
- Conciseness rules (1-2 sentences)
- Greeting response templates
- Language consistency rules

### Escalation Templates
- **`escalation_fr.txt`** - French escalation messages
- **`escalation_en.txt`** - English escalation messages

**Contains:**
- 3 escalation levels: URGENT, HIGH, NORMAL
- Manager contact info templates
- Callback markers: `[CALLBACK_URGENT]`, `[CALLBACK_HIGH]`, `[CALLBACK_NORMAL]`

### RAG/Knowledge Base
- **`rag_instructions_fr.txt`** - French RAG guidelines
- **`rag_instructions_en.txt`** - English RAG guidelines

**Contains:**
- When to search knowledge base
- How to cite sources
- Tool usage: `search_documents`

### Identity & Consistency
- **`identity_rules.txt`** - Universal identity rules (all languages)

**Contains:**
- AI identity enforcement
- Speech consistency rules
- Character maintenance

## 🔧 How to Edit Prompts

### 1. Open the Template File
```bash
# Example: Edit French conversation style
notepad backend/app/prompts/conversation_style_fr.txt
```

### 2. Variables Available
Use these placeholders in your prompts:
- `{agent_name}` - Replaced with agent's name
- `{manager_contact}` - Replaced with manager contact info

### 3. Save and Restart
Changes take effect immediately on next agent interaction!

## 🌍 Adding New Languages

Want to add Spanish, German, or other languages?

### Step 1: Create Template Files
```
backend/app/prompts/conversation_style_es.txt
backend/app/prompts/escalation_es.txt
backend/app/prompts/rag_instructions_es.txt
```

### Step 2: Update Services
In `text_chat_service.py` and `agent_service.py`, add language detection:

```python
if self.agent.language.startswith('es'):
    lang_suffix = 'es'
elif self.agent.language.startswith('fr'):
    lang_suffix = 'fr'
else:
    lang_suffix = 'en'
```

## 📋 Prompt Loading Code

### In Text Chat Service
```python
from app.prompts import load_prompt

# Load prompts
conversation_style = load_prompt(f'conversation_style_{lang_suffix}.txt')
escalation_msg = load_prompt(f'escalation_{lang_suffix}.txt')
```

### In Voice Call Service
```python
from app.prompts import load_prompt

# Same loading method
conversation_style = load_prompt(f'conversation_style_{lang_suffix}.txt')
```

## ✅ Testing Your Changes

### 1. Test Text Chat
- Open dashboard → Agents → Test button
- Try greetings: "Hello", "Bonjour"
- Try escalation: "I need to speak to a manager"

### 2. Test Voice Call
- Make a test call to your agent
- Say greetings and check responses
- Test escalation scenarios

## 🎨 Customization Examples

### Make Agent More Casual
Edit `conversation_style_en.txt`:
```
- Use casual language: "Hey!", "Sure thing!", "No problem!"
- Be super friendly and upbeat
```

### Make Agent More Formal
Edit `conversation_style_en.txt`:
```
- Use formal language: "Good day", "Certainly", "I would be pleased to assist"
- Maintain professional distance
```

### Change Escalation Tone
Edit `escalation_en.txt`:
```
1. URGENT - More empathetic:
   → "[CALLBACK_URGENT] I completely understand how frustrating this must be. 
       Our senior manager will prioritize your case. Can I have your contact details?"
```

## 🚀 Pro Tips

1. **Keep it Short**: Agents work best with concise prompts
2. **Be Specific**: Clear instructions = better responses
3. **Test Changes**: Always test after editing prompts
4. **Version Control**: Commit prompt changes to git
5. **A/B Testing**: Try different versions and compare results

## 📦 Migration Required

After pulling these changes, run:

```bash
cd backend
python database/migrations/run_manager_contact_migration.py
```

This adds the `manager_contact` field to agents.

## 🔍 Troubleshooting

### Prompt Not Loading?
Check file encoding is **UTF-8** (not UTF-8-BOM)

### Variables Not Replaced?
Ensure exact syntax: `{agent_name}` not `{{agent_name}}`

### Language Not Working?
Check agent's language setting matches template filename suffix

---

**Need help?** Check `CONVERSATION_OPTIMIZATION_COMPLETE.md` for full documentation!

