-- Community Emergency & Resource Dispatcher
-- Run this in the Supabase SQL editor to set up the schema.

create table if not exists users (
    id serial primary key,
    name text not null,
    email text not null unique,
    password_hash text not null,
    role text not null check (role in ('citizen', 'coordinator')),
    created_at timestamptz not null default now()
);

create table if not exists requests (
    id serial primary key,
    citizen_id integer not null references users(id) on delete cascade,
    category text not null,
    description text not null,
    urgency text not null check (urgency in ('critical', 'high', 'medium', 'low')),
    latitude real,
    longitude real,
    status text not null default 'pending' check (status in ('pending', 'dispatched', 'resolved')),
    synced_offline boolean not null default false,
    quantity_needed real not null default 1,
    quantity_fulfilled real not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists offers (
    id serial primary key,
    citizen_id integer not null references users(id) on delete cascade,
    resource_type text not null,
    description text not null,
    quantity integer,
    quantity_remaining real,
    latitude real,
    longitude real,
    status text not null default 'available' check (status in ('available', 'dispatched', 'resolved')),
    synced_offline boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists dispatches (
    id serial primary key,
    request_id integer not null references requests(id) on delete cascade,
    offer_id integer not null references offers(id) on delete cascade,
    coordinator_id integer not null references users(id),
    quantity real not null,
    contact_name text,
    contact_phone text,
    meetup_location text,
    meetup_notes text,
    status text not null default 'active' check (status in ('active', 'completed', 'cancelled')),
    created_at timestamptz not null default now()
);

create table if not exists matches (
    id serial primary key,
    request_id integer not null references requests(id) on delete cascade,
    offer_id integer not null references offers(id) on delete cascade,
    score real not null,
    distance_km real,
    created_at timestamptz not null default now()
);

create table if not exists status_audit_log (
    id serial primary key,
    entity_type text not null check (entity_type in ('request', 'offer')),
    entity_id integer not null,
    old_status text,
    new_status text not null,
    changed_by integer references users(id),
    note text,
    changed_at timestamptz not null default now()
);

-- Helpful indexes for the dashboard queries
create index if not exists idx_requests_status on requests(status);
create index if not exists idx_offers_status on offers(status);
create index if not exists idx_matches_request on matches(request_id);
create index if not exists idx_matches_offer on matches(offer_id);
create index if not exists idx_audit_entity on status_audit_log(entity_type, entity_id);
create index if not exists idx_dispatches_request on dispatches(request_id);
create index if not exists idx_dispatches_offer on dispatches(offer_id);

-- Safe to re-run against an existing (pre-dispatch-feature) database:
-- adds the new columns if this schema was applied before they existed.
alter table requests add column if not exists quantity_needed real not null default 1;
alter table requests add column if not exists quantity_fulfilled real not null default 0;
alter table offers add column if not exists quantity_remaining real;
