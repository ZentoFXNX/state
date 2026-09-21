CREATE EXTENSION IF NOT EXISTS pg_trickle;

SELECT pgtrickle.create_stream_table_if_not_exists(
	'sales_by_category',
	'SELECT category_id,
			count(*) AS row_count,
			sum(amount) AS total_amount,
			avg(amount) AS average_amount
	 FROM fact_sales
	 GROUP BY category_id',
	schedule => '1d',
	refresh_mode => 'DIFFERENTIAL'
);

SELECT pgtrickle.create_stream_table_if_not_exists(
	'sales_by_category_full',
	'SELECT category_id,
			count(*) AS row_count,
			sum(amount) AS total_amount,
			avg(amount) AS average_amount
	 FROM fact_sales
	 GROUP BY category_id',
	schedule => '1d',
	refresh_mode => 'FULL'
);
