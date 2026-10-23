INSERT INTO customers VALUES ('cus_001','Example Workshop','standard'),('cus_002','Example Studio','plus');
INSERT INTO orders VALUES
 ('ord_001','cus_001',12900,'pending','2026-10-01'),
 ('ord_002','cus_001',4500,'shipped','2026-10-02'),
 ('ord_003','cus_001',9900,'cancelled','2026-10-03'),
 ('ord_004','cus_002',22000,'pending','2026-10-04');
INSERT INTO invoices VALUES
 ('inv_001','cus_001','ord_001',12900,'open','2026-11-01'),
 ('inv_002','cus_001','ord_002',4500,'paid','2026-10-15'),
 ('inv_003','cus_001','ord_003',9900,'overdue','2026-10-01'),
 ('inv_004','cus_002','ord_004',22000,'open','2026-11-04');
