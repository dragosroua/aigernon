---
name: add-realm-detection
description: Centralized ADD realm detection patterns for identifying user cognitive state
metadata: {"aigernon":{"emoji":"🔍","always":true}}
---

# ADD Realm Detection

Detect which realm a user is in based on language, behavior, and context.

## Detection Philosophy

- **Implicit** — Don't announce "I detect you're in Assess mode"
- **Pattern-based** — Look for clusters, not single indicators
- **Context-aware** — Consider conversation flow
- **Non-judgmental** — Detection informs response, not correction

## ASSESS Detection

**High-confidence language:**
- "I'm thinking about...", "What are my options...", "Help me understand..."
- "What if I...", "I'm curious about...", "Can you explain..."

**Modality:** "might", "could", "would if", "considering"
**Commitment:** Low — "maybe", "thinking about", "not sure"

**Behaviors:** Research requests, multiple options, brainstorming, processing new inputs

## DECIDE Detection

**High-confidence language:**
- "Should I...", "I need to choose between...", "What's the priority..."
- "I want to commit to...", "Help me decide...", "I'm leaning toward..."

**Modality:** "I want to", "I'm choosing", "This matters"
**Commitment:** Medium-High — "leaning toward", "drawn to", "I've decided"

**Behaviors:** Comparing options, weighing trade-offs, setting priorities

## DO Detection

**High-confidence language:**
- "How do I actually...", "Walk me through the steps..."
- "I'm working on...", "What's the next step...", "Help me finish..."

**Modality:** "I'm doing", "working on", "completing"
**Commitment:** Execution mode — "let's do this", "next step", "implementing now"

**Behaviors:** Step-by-step requests, progress updates, not questioning whether to do it

## Transition Signals

**Assess → Decide:**
- "I think I have enough information"
- "OK, so my options are basically..."
- Shift from "what if" to "which one"

**Decide → Do:**
- "OK, I've decided", "Let's do it"
- Confident past-tense about choice
- Shift from "which" to "how"

**Do → Assess:**
- "Done!", "That's finished", "What else?"
- Natural pause after execution

## Confidence Assessment

**High:** Multiple signals, consistent context → Fully align to realm
**Medium:** Mixed but predominant pattern → Respond to predominant, stay flexible
**Low:** Conflicting signals → Gently probe before committing
