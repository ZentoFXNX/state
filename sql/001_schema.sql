CREATE TABLE IF NOT EXISTS fact_sales (
    id          bigint PRIMARY KEY,
    customer_id bigint NOT NULL,
    category_id integer NOT NULL,
    amount      numeric(12, 2) NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS fact_sales_category_idx ON fact_sales(category_id);
CREATE INDEX IF NOT EXISTS fact_sales_customer_idx ON fact_sales(customer_id);
