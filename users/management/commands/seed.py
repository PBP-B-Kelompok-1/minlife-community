"""Populate the local database with representative development data."""
# https://chatgpt.com/s/cx_6ae4a5102a3481919bac2fa597c2ee2a

from datetime import timedelta
import random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from announcements.models import Announcement, FCMSubscription
from journal.models import JournalEntry
from posts.models import Comment, Post, Tag, Vote
from users.models import Badge, Follow, SocialLink, SocialPlatform, UserBadge
from weeklychallenge.models import Challenge, ChallengeSubmission, ChallengeTask


class Command(BaseCommand):
    help = "Seed representative development data for every Minlife module."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Number of primary records to create per module (minimum: 50).",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Flush all database data before seeding. This cannot be undone.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20261030,
            help="Random seed, for reproducible sample data.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        if count < 50:
            raise CommandError("--count must be at least 50.")

        if options["clean"]:
            # `flush` preserves the schema and re-runs post-migrate handlers.
            # It is deliberately opt-in because it removes *all* database data.
            call_command("flush", interactive=False, verbosity=0)

        rng = random.Random(options["seed"])
        User = get_user_model()
        moderator_group, _ = Group.objects.get_or_create(name="Moderator")
        moderator_permissions = [
            ("posts", "delete_post"), ("posts", "delete_comment"),
            ("posts", "add_tag"), ("posts", "change_tag"), ("posts", "delete_tag"),
            ("announcements", "add_announcement"),
            ("announcements", "change_announcement"),
            ("announcements", "delete_announcement"),
            ("weeklychallenge", "add_challenge"),
            ("weeklychallenge", "change_challenge"),
            ("weeklychallenge", "delete_challenge"),
        ]
        moderator_group.permissions.add(*[
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
            for app_label, codename in moderator_permissions
        ])

        moderator, _ = User.objects.get_or_create(
            username="seed_moderator",
            defaults={
                "email": "moderator@example.test",
                "first_name": "Minlife",
                "last_name": "Moderator",
                "bio": "Moderator account created by the development seed command.",
                "is_staff": True,
            },
        )
        moderator.set_password("seed-password")
        moderator.save(update_fields=["password"])
        moderator.groups.add(moderator_group)

        users = []
        first_names = ["Alya", "Bima", "Citra", "Dimas", "Elara", "Farhan", "Gita", "Hana"]
        last_names = ["Pratama", "Wijaya", "Lestari", "Putri", "Nugroho", "Sari", "Mahendra"]
        bios = [
            "Learning to own less and notice more.",
            "Making room for slow mornings and good books.",
            "Trying one small decluttering habit each week.",
            "Interested in mindful spending and sustainable choices.",
            "Here for practical, judgement-free minimalism.",
        ]
        for index in range(count):
            user, created = User.objects.get_or_create(
                username=f"seed_user_{index + 1:03d}",
                defaults={
                    "email": f"seed_user_{index + 1:03d}@example.test",
                    "first_name": rng.choice(first_names),
                    "last_name": rng.choice(last_names),
                    "bio": rng.choice(bios),
                    "avatar_url": f"https://i.pravatar.cc/300?img={(index % 70) + 1}",
                },
            )
            if created:
                user.set_password("seed-password")
                user.save(update_fields=["password"])
            users.append(user)

        for index, user in enumerate(users):
            SocialLink.objects.get_or_create(
                user=user,
                platform=rng.choice(SocialPlatform.values),
                defaults={"url": f"https://example.test/seed_user_{index + 1:03d}"},
            )
            for following in rng.sample([candidate for candidate in users if candidate != user], k=rng.randint(1, 3)):
                Follow.objects.get_or_create(follower=user, following=following)

        tag_names = [
            "Question", "Article", "Poll", "Selling/Giveaway", "Decluttering",
            "Mindfulness", "Sustainable Living", "Weekly Challenge",
        ]
        tags = {title: Tag.objects.get_or_create(title=title)[0] for title in tag_names}

        posts = []
        post_ideas = [
            ("How I simplified my workspace", "I cleared my desk in short sessions and noticed that a clear surface made starting work much easier."),
            ("A calmer digital routine", "Turning off non-essential notifications gave me a little more attention for the things I chose to do."),
            ("What I stopped buying", "I now wait a week before buying a non-essential item. Most of the time, the urge passes."),
            ("One drawer at a time", "A single untidy drawer felt achievable. I kept what I use, donated what could help someone else, and recycled the rest."),
            ("Small changes, lighter days", "A lighter routine is not about perfection. It is about leaving enough space to breathe."),
            ("My low-waste kitchen reset", "I used up pantry staples before replacing them and found several meals I had forgotten I liked."),
            ("Borrowing before buying", "Borrowing a tool from a neighbour was simpler than storing one I may only need once."),
        ]
        for index in range(count):
            topic, body = rng.choice(post_ideas)
            post, _ = Post.objects.get_or_create(
                title=f"[Seed {index + 1:03d}] {topic}",
                defaults={
                    "author": rng.choice(users),
                    "content": body,
                },
            )
            post.tags.set(rng.sample(list(tags.values())[:-1], k=rng.randint(1, 3)))
            posts.append(post)

        # Thirty conversations are deliberately threaded, so the post UI has
        # roots, replies, and replies-to-replies to render during development.
        replies = [
            "I tried this too, and the small starting point really helped.",
            "That is a thoughtful way to look at it. What did you find hardest?",
            "Great reminder that a useful system does not need to be complicated.",
            "I appreciate the practical example—saving this for the weekend.",
            "This makes me want to start with one shelf instead of the whole room.",
        ]
        for index, post in enumerate(posts):
            root, _ = Comment.objects.get_or_create(
                post=post,
                user=rng.choice(users),
                content=f"[Seed thread {index + 1:03d}] {rng.choice(replies)}",
            )
            Vote.objects.get_or_create(
                user=rng.choice(users), post=post,
                defaults={"value": rng.choice([-1, 1, 1, 1])},
            )
            Vote.objects.get_or_create(
                user=rng.choice(users), comment=root,
                defaults={"value": rng.choice([-1, 1, 1])},
            )
            if index < min(30, count):
                reply, _ = Comment.objects.get_or_create(
                    post=post, user=rng.choice(users), replies_to_comment=root,
                    content=f"[Seed reply {index + 1:03d}.1] {rng.choice(replies)}",
                )
                Vote.objects.get_or_create(user=rng.choice(users), comment=reply, defaults={"value": 1})
                if index % 2 == 0:
                    nested_reply, _ = Comment.objects.get_or_create(
                        post=post, user=rng.choice(users), replies_to_comment=reply,
                        content=f"[Seed reply {index + 1:03d}.2] {rng.choice(replies)}",
                    )
                    Vote.objects.get_or_create(user=rng.choice(users), comment=nested_reply, defaults={"value": 1})

        announcement_topics = [
            ("Community swap this Saturday", "Bring a clean, useful item you no longer need and take home only something you will use."),
            ("A note about kind discussions", "Please challenge ideas with care and assume good intent when someone is starting out."),
            ("New weekly challenge is live", "This week we are making our everyday spaces easier to maintain."),
            ("Tips for a calmer feed", "Use tags and follows to keep your community feed useful and welcoming."),
            ("Volunteer moderation update", "Thank you to everyone who reports content that needs a second look."),
        ]
        for index in range(count):
            announcement_title, announcement_content = rng.choice(announcement_topics)
            Announcement.objects.get_or_create(
                title=f"[Seed {index + 1:03d}] {announcement_title}",
                defaults={
                    "created_by": moderator,
                    "content": announcement_content,
                },
            )
            FCMSubscription.objects.get_or_create(
                installation_id=f"seed-installation-{index + 1:03d}",
                defaults={"user": rng.choice(users)},
            )

        today = timezone.localdate()
        journal_prompts = [
            "I noticed one thing I own but do not use, and made a plan for it.",
            "Today felt calmer after I protected an hour without notifications.",
            "I am grateful for a routine that makes my space easier to reset.",
            "I paused before buying something and wrote down why I wanted it.",
            "A small tidy-up made the rest of my day feel more manageable.",
        ]
        for index in range(count):
            JournalEntry.objects.get_or_create(
                user=users[index % len(users)],
                date=today - timedelta(days=(index // len(users)) * 2),
                defaults={
                    "content": f"[Seed journal {index + 1:03d}] {rng.choice(journal_prompts)}",
                    "visibility": rng.choice([JournalEntry.Visibility.PUBLIC, JournalEntry.Visibility.PRIVATE]),
                },
            )

        # Separate challenge weeks guarantee there is no overlap.  The final one
        # is the current week, which also gives the UI an active challenge.
        challenge_themes = [
            ("Clear one small space", "Visual clutter can make it harder to focus.", "Create a calmer, easier-to-maintain daily environment."),
            ("Digital inbox reset", "Unanswered messages and notifications can compete for attention.", "Build a more intentional relationship with your devices."),
            ("Use what you have", "Duplicate purchases often hide in cupboards and drawers.", "Notice and enjoy resources already at home."),
            ("Simplify a daily routine", "Too many small decisions can drain energy over time.", "Make one everyday routine easier to repeat."),
            ("Mindful wardrobe edit", "An overcrowded wardrobe can make getting dressed feel needlessly difficult.", "Keep a wardrobe that supports your actual life."),
        ]
        task_actions = [
            "Choose one small area", "Set a ten-minute timer", "Separate keep and let-go items",
            "Clean the newly clear surface", "Donate or recycle one item", "Notice what feels easier", "Plan a gentle reset habit",
        ]
        challenges = []
        for index in range(count):
            week_start = today - timedelta(days=(count - 1 - index) * 7)
            challenge_title, background, goal = rng.choice(challenge_themes)
            badge, _ = Badge.objects.get_or_create(
                name=f"[Seed {index + 1:03d}] {challenge_title} Badge",
                defaults={"description": "Awarded for completing a seeded weekly challenge."},
            )
            challenge, _ = Challenge.objects.get_or_create(
                title=f"[Seed {index + 1:03d}] {challenge_title}",
                defaults={
                    "background": background,
                    "description": f"For seven days, {challenge_title.lower()} in a way that feels achievable for you.",
                    "goal": goal,
                    "badge": badge,
                    "week_start": week_start,
                    "created_by": moderator,
                    "upvote_threshold": rng.randint(2, 8),
                },
            )
            challenges.append(challenge)
            for day in range(1, 8):
                ChallengeTask.objects.get_or_create(
                    challenge=challenge,
                    day_number=day,
                    defaults={
                        "title": task_actions[day - 1],
                        "description": rng.choice([
                            "Keep the task small enough to finish today.",
                            "Take a photo or make a note about what changed.",
                            "Focus on usefulness rather than perfection.",
                        ]),
                    },
                )

        # Seed a leaderboard/history for every challenge.  These are historical
        # records, so they are created directly rather than through the active-
        # challenge signal used by the normal post submission flow.
        for index, challenge in enumerate(challenges):
            user = rng.choice(users)
            post, _ = Post.objects.get_or_create(
                title=f"[Seed submission {index + 1:03d}] {challenge.title}",
                defaults={
                    "author": user,
                    "content": rng.choice([
                        "I completed today’s task and found a few easy items to pass along.",
                        "A short session was enough to make the space feel more usable.",
                        "I focused on progress instead of trying to do everything at once.",
                    ]),
                },
            )
            # Historical seed submissions are assigned explicitly below. Add
            # the M2M row directly so the live m2m_changed handler does not
            # attach every historical Post to today's active challenge.
            Post.tags.through.objects.get_or_create(
                post_id=post.pk,
                tag_id=tags["Weekly Challenge"].pk,
            )
            ChallengeSubmission.objects.get_or_create(
                challenge=challenge,
                user=user,
                defaults={"post": post},
            )
            UserBadge.objects.get_or_create(user=user, badge=challenge.badge)

        self.stdout.write(self.style.SUCCESS(
            "Seed complete: "
            f"{User.objects.count()} users, {Post.objects.count()} posts, "
            f"{Announcement.objects.count()} announcements, "
            f"{JournalEntry.objects.count()} journal entries, and "
            f"{Challenge.objects.count()} challenges."
        ))
