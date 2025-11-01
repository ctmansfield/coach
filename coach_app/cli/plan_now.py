import argparse, os, datetime as dt
from dateutil import tz
from coach_app.motivation.engine import suggestions
from coach_app.motivation.bandit import choose_arm
from coach_app.clients.mother import predict, create_reminder

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--hours", type=int, default=4)
    p.add_argument("--goals", type=str, default="deep_work,hydration,walk")
    args = p.parse_args()

    # get expectancy from mother
    pr = predict("adherence_risk_v1", {"recent_skips": 1, "last_streak": 2})
    expectancy = pr.get("prediction", {}).get("expectancy", 0.6)

    sugs = suggestions({"expectancy": expectancy})
    now = dt.datetime.now(tz=tz.tzlocal())
    arm = choose_arm()

    created = []
    for s in sugs[:3]:
        due = now + dt.timedelta(minutes=5 if s["title"]=="Hydrate" else 30)
        rec = {
            "user_id": args.user,
            "title": s["title"],
            "note": f"{s['tiny_step']} [{arm['style']} · {arm['cta']}]",
            "due_at": due.astimezone(tz=tz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "channel": "email"
        }
        created.append(create_reminder(rec))
    print(f"Created {len(created)} reminders")
    for c in created:
        print(c)

if __name__ == "__main__":
    main()
