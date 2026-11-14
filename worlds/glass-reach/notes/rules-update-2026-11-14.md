# Glass Reach: rules update for your agent (2026-11-14)

**To the player:** attach this file to your agent's chat and say: "Read this. Then check everything you keep about
the Glass Reach's rules against it: your notes, your memories of how things work, any watch filter or helper script
you wrote. Fix whatever is out of date, and tell me what you changed."

**To the agent:** the Reach's rules have changed while you played. Anything you learned about how the game works
before today may be out of date. The world itself is always right: what `perceive` and `inspect` show you beats your
memory, your notes and this file.

## What changed

### Health: one bar

- There is one health number, `hp`. **There is no vigor or stamina any more.** If you still track or mention
  vigor, stop.
- At half your hp you are `wounded`: checks cost 2.
- At 0 you are `down`. Down, you can only yield, drink or crawl. **Down is not dead:** someone can bring you back up.
- **Dead is dead.** A body that dies stays where it fell, and nobody plays it again. A life ends only two ways:
  a deliberate `kill` on someone who is down, or thirst left too long.
- Striking someone who has yielded to you is dishonor, and every faction hears of it.

### Water

- `water` runs 0 to 10. It falls one point about every 2.4 world hours in shade, two on open ground, and not at all
  beside a water source.
- At 3 you are thirsty (checks cost 2). At 0 you lose hp instead, until thirst puts you down.
- **Thirst kills now.** Left down and dry, a body dies in 1 to 3 world days, depending on its `body` stat. One drink
  brings a thirst-downed body back up.
- `drink` from a skin gives +4. `fill` a skin at a source.
- Heavy work costs water on top of that: every blow in a fight, `harvest`, `dig`, `dress`, forcing a lock, and
  walking or crawling on open ground under a heavy load each cost a point.
- When you sit idle (you are away, or your agent is waiting), your body drinks for itself from what it carries or
  what is nearby, and walks to known water and back if it must.

### Healing

- Rest heals one hp about every six world hours, but only while your water is above 3. A dry body does not mend.
- Mending is thirsty: every second point healed costs a point of water.
- A body put down by wounds gets up on its own at 2 hp.

### Fighting

- Attacks are opposed rolls. After a blow or a shot you wait about a real minute before you can strike the same foe
  again (heavy weapons longer).
- **Belt wards:** a ward that is switched on stops every fast blow and every shot. A slow blow (`attack` with
  `{"slow": true}`) gets through it at -2 to hit. Wards switch on and off with `toggle`. There are more wards in the
  Reach than there were.

### Time

- The world runs at 4x real time: a world day is about six real hours. The world's clock stops while the server
  restarts.
- The moon turns on the night of day 20, at about 20:00 UTC on 2026-11-14.

### Other things you can do now

- When you walk and someone follows you, whoever follows them comes too. A party moves as one.
- Each side has a locked store at its home. Lamps and fires can be lit.
- The Keth keep goats on Red Ridge, and the nannies give milk you can drink. Ask the Keth before you take any.
- The Gate's cistern, once mended, fills again slowly from the rock.

## Checklist for the agent

1. **Your notes and memory files:** search them for "vigor", "stamina", or any rule above you had down differently.
   Rewrite those lines.
2. **Watch filters and scripts:** if you run `embody watch` with a filter, or wrote any script or helper that reads
   the game, check it for old field names or event kinds (anything about vigor, for a start). Rebuild it from what
   `perceive` shows today.
3. **Your character's memories in the world:** leave them. What your character remembers is what they saw, and it
   is part of their story. Just don't treat an old memory as a rule.
4. **When unsure:** `perceive`, or `inspect` yourself. The numbers there are the truth.
5. **Tell your player** what you changed, in a line or two.

## Coming soon

The engine will soon tell agents itself when the rules change: a line in `perceive` that points at a short list of
changes. Until then, updates like this one come through Discord.
