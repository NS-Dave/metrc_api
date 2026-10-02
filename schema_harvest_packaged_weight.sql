-- 2026-10-02: packaged (dry) weight per harvest, needed for strain yield in 140 costing.
ALTER TABLE public.metrc_harvests
    ADD COLUMN IF NOT EXISTS "totalPackagedWeight" numeric;
