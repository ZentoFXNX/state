GRANT USAGE ON SCHEMA public, pgtrickle, pgtrickle_changes TO experiment;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON public.fact_sales TO experiment;
GRANT ALL PRIVILEGES ON public.sales_by_category, public.sales_by_category_full TO experiment;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA pgtrickle TO experiment;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA pgtrickle TO experiment;
GRANT INSERT, SELECT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA pgtrickle_changes TO experiment;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pgtrickle_changes TO experiment;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pgtrickle, pgtrickle_changes TO experiment;
