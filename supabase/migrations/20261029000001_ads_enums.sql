-- Ads pivot: new track + pilot lead statuses. Enum values live in their own file because a new
-- value can't be used in the same transaction that adds it.
alter type track add value if not exists 'ads';
alter type lead_status add value if not exists 'pilot_onboarding';   -- said yes: collecting 5 answers / access / payment
alter type lead_status add value if not exists 'pilot_live';         -- ads running
alter type lead_status add value if not exists 'pilot_review';       -- day 7 done, awaiting decision
