
DROP DATABASE IF EXISTS airline_db;
CREATE DATABASE airline_db;
USE airline_db;

-- =========================
-- COUNTRY
-- =========================
CREATE TABLE COUNTRY (
    country_id CHAR(4) PRIMARY KEY,
    country_name VARCHAR(80) UNIQUE
);

INSERT INTO COUNTRY VALUES
('C001','Pakistan'),
('C002','UAE'),
('C003','UK'),
('C004','USA'),
('C005','Qatar'),
('C006','Germany'),
('C007','Turkey');

-- =========================
-- CITY
-- =========================
CREATE TABLE CITY (
    city_id CHAR(6) PRIMARY KEY,
    city_name VARCHAR(80),
    country_id CHAR(4),
    FOREIGN KEY (country_id) REFERENCES COUNTRY(country_id)
);

INSERT INTO CITY VALUES
('CT001','Karachi','C001'),
('CT002','Lahore','C001'),
('CT003','Dubai','C002'),
('CT004','London','C003'),
('CT005','New York','C004'),
('CT006','Doha','C005'),
('CT007','Istanbul','C007');

-- =========================
-- AIRPORT
-- =========================
CREATE TABLE AIRPORT (
    airport_id CHAR(6) PRIMARY KEY,
    iata_code CHAR(3) UNIQUE,
    name VARCHAR(120),
    city_id CHAR(6),
    FOREIGN KEY (city_id) REFERENCES CITY(city_id),
    CHECK (iata_code REGEXP '^[A-Z]{3}$')
);

INSERT INTO AIRPORT VALUES
('APT001','KHI','Jinnah Intl','CT001'),
('APT002','LHE','Allama Iqbal','CT002'),
('APT003','DXB','Dubai Intl','CT003'),
('APT004','LHR','Heathrow','CT004'),
('APT005','JFK','JFK Airport','CT005'),
('APT006','DOH','Hamad Intl','CT006'),
('APT007','IST','Istanbul Airport','CT007');

-- =========================
-- AIRLINE
-- =========================
CREATE TABLE AIRLINE (
    airline_id CHAR(6) PRIMARY KEY,
    iata_code CHAR(2) UNIQUE,
    name VARCHAR(120),
    country_id CHAR(4),
    FOREIGN KEY (country_id) REFERENCES COUNTRY(country_id)
);

INSERT INTO AIRLINE VALUES
('AIR001','PK','PIA','C001'),
('AIR002','EK','Emirates','C002'),
('AIR003','BA','British Airways','C003'),
('AIR004','QR','Qatar Airways','C005'),
('AIR005','LH','Lufthansa','C006'),
('AIR006','TK','Turkish Airlines','C007'),
('AIR007','AA','American Airlines','C004');

-- =========================
-- AIRCRAFT MODEL
-- =========================
CREATE TABLE AIRCRAFT_MODEL (
    model_id INT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(50),
    total_seats INT
);

INSERT INTO AIRCRAFT_MODEL (model_name,total_seats) VALUES
('Boeing737',180),
('A380',500),
('Boeing777',350),
('A320',150),
('A350',300),
('Boeing787',250),
('A330',280);

-- =========================
-- AIRCRAFT
-- =========================
CREATE TABLE AIRCRAFT (
    aircraft_id CHAR(8) PRIMARY KEY,
    model_id INT,
    airline_id CHAR(6),
    FOREIGN KEY (model_id) REFERENCES AIRCRAFT_MODEL(model_id),
    FOREIGN KEY (airline_id) REFERENCES AIRLINE(airline_id)
);

INSERT INTO AIRCRAFT VALUES
('AC001',1,'AIR001'),
('AC002',2,'AIR002'),
('AC003',3,'AIR002'),
('AC004',4,'AIR003'),
('AC005',5,'AIR004'),
('AC006',6,'AIR006'),
('AC007',7,'AIR007');

-- =========================
-- SEAT CLASS
-- =========================
CREATE TABLE SEAT_CLASS (
    class_id INT PRIMARY KEY AUTO_INCREMENT,
    class_name VARCHAR(20) UNIQUE
);

INSERT INTO SEAT_CLASS (class_name) VALUES
('Economy'),
('Business'),
('First'),
('Premium Economy'),
('VIP'),
('Crew'),
('Extra');

-- =========================
-- SEAT
-- =========================
CREATE TABLE SEAT (
    seat_id CHAR(8) PRIMARY KEY,
    seat_number VARCHAR(5),
    class_id INT,
    aircraft_id CHAR(8),
    UNIQUE (aircraft_id, seat_number),
    FOREIGN KEY (class_id) REFERENCES SEAT_CLASS(class_id),
    FOREIGN KEY (aircraft_id) REFERENCES AIRCRAFT(aircraft_id)
);

INSERT INTO SEAT VALUES
('S1','1A',1,'AC001'),
('S2','1B',2,'AC001'),
('S3','2A',3,'AC002'),
('S4','10A',4,'AC003'),
('S5','12B',1,'AC004'),
('S6','14C',2,'AC005'),
('S7','20D',3,'AC006');

-- =========================
-- ROUTE
-- =========================
CREATE TABLE ROUTE (
    route_id CHAR(8) PRIMARY KEY,
    departure_airport CHAR(6),
    arrival_airport CHAR(6),
    distance INT,
    FOREIGN KEY (departure_airport) REFERENCES AIRPORT(airport_id),
    FOREIGN KEY (arrival_airport) REFERENCES AIRPORT(airport_id)
);

INSERT INTO ROUTE VALUES
('R1','APT001','APT003',1500),
('R2','APT001','APT004',6000),
('R3','APT003','APT005',12000),
('R4','APT004','APT005',5500),
('R5','APT005','APT006',11000),
('R6','APT006','APT007',2000),
('R7','APT002','APT003',1400);

-- =========================
-- FLIGHT
-- =========================
CREATE TABLE FLIGHT (
    flight_id CHAR(8) PRIMARY KEY,
    status ENUM('Scheduled','Delayed','Cancelled'),
    departure_time DATETIME,
    arrival_time DATETIME,
    route_id CHAR(8),
    aircraft_id CHAR(8),
    airline_id CHAR(6),
    FOREIGN KEY (route_id) REFERENCES ROUTE(route_id),
    FOREIGN KEY (aircraft_id) REFERENCES AIRCRAFT(aircraft_id),
    FOREIGN KEY (airline_id) REFERENCES AIRLINE(airline_id)
);

INSERT INTO FLIGHT VALUES
('F1','Scheduled','2025-06-01 08:00','2025-06-01 10:00','R1','AC001','AIR001'),
('F2','Scheduled','2025-06-02 09:00','2025-06-02 16:00','R2','AC002','AIR002'),
('F3','Delayed','2025-06-03 10:00','2025-06-03 18:00','R3','AC003','AIR002'),
('F4','Scheduled','2025-06-04 11:00','2025-06-04 14:00','R4','AC004','AIR003'),
('F5','Cancelled','2025-06-05 06:00','2025-06-05 09:00','R5','AC005','AIR004'),
('F6','Scheduled','2025-06-06 07:00','2025-06-06 12:00','R6','AC006','AIR006'),
('F7','Scheduled','2025-06-07 09:00','2025-06-07 13:00','R7','AC007','AIR007');

-- =========================
-- PASSENGER
-- =========================
CREATE TABLE PASSENGER (
    passenger_id CHAR(8) PRIMARY KEY,
    name VARCHAR(100),
    passport_no VARCHAR(20) UNIQUE,
    dob DATE
);

INSERT INTO PASSENGER VALUES
('P1','Ali Khan','PK123','1990-01-01'),
('P2','Sara Ali','PK124','1992-02-02'),
('P3','John Doe','US123','1980-03-03'),
('P4','Emma Watson','UK123','1985-04-04'),
('P5','Ahmed Raza','PK125','1995-05-05'),
('P6','Omar Khan','PK126','1993-06-06'),
('P7','David Smith','US124','1988-07-07');

-- =========================
-- BOOKING
-- =========================
CREATE TABLE BOOKING (
    booking_id CHAR(10) PRIMARY KEY,
    passenger_id CHAR(8),
    flight_id CHAR(8),
    seat_id CHAR(8),
    FOREIGN KEY (passenger_id) REFERENCES PASSENGER(passenger_id),
    FOREIGN KEY (flight_id) REFERENCES FLIGHT(flight_id),
    FOREIGN KEY (seat_id) REFERENCES SEAT(seat_id),
    UNIQUE (flight_id, seat_id)
);

INSERT INTO BOOKING VALUES
('B1','P1','F1','S1'),
('B2','P2','F2','S2'),
('B3','P3','F3','S3'),
('B4','P4','F4','S4'),
('B5','P5','F5','S5'),
('B6','P6','F6','S6'),
('B7','P7','F7','S7');

-- =========================
-- PAYMENT
-- =========================
CREATE TABLE PAYMENT (
    payment_id CHAR(10) PRIMARY KEY,
    amount DECIMAL(10,2),
    status ENUM('Pending','Completed'),
    booking_id CHAR(10),
    FOREIGN KEY (booking_id) REFERENCES BOOKING(booking_id)
);

INSERT INTO PAYMENT VALUES
('PAY1',20000,'Completed','B1'),
('PAY2',15000,'Completed','B2'),
('PAY3',30000,'Pending','B3'),
('PAY4',50000,'Completed','B4'),
('PAY5',10000,'Pending','B5'),
('PAY6',25000,'Completed','B6'),
('PAY7',18000,'Pending','B7');

-- =========================
-- BAGGAGE
-- =========================
CREATE TABLE BAGGAGE (
    baggage_id CHAR(10) PRIMARY KEY,
    weight DECIMAL(5,2),
    booking_id CHAR(10),
    FOREIGN KEY (booking_id) REFERENCES BOOKING(booking_id)
);

INSERT INTO BAGGAGE VALUES
('BG1',20,'B1'),
('BG2',18,'B2'),
('BG3',25,'B3'),
('BG4',22,'B4'),
('BG5',19,'B5'),
('BG6',24,'B6'),
('BG7',21,'B7');

-- =========================
-- CREW
-- =========================
CREATE TABLE CREW (
    crew_id CHAR(8) PRIMARY KEY,
    name VARCHAR(100)
);

INSERT INTO CREW VALUES
('C1','Pilot A'),
('C2','CoPilot B'),
('C3','Attendant C'),
('C4','Pilot D'),
('C5','Engineer E'),
('C6','Pilot F'),
('C7','Attendant G');

-- =========================
-- FLIGHT CREW
-- =========================
CREATE TABLE FLIGHT_CREW (
    flight_id CHAR(8),
    crew_id CHAR(8),
    role ENUM('Pilot','CoPilot','Attendant'),
    PRIMARY KEY (flight_id, crew_id),
    FOREIGN KEY (flight_id) REFERENCES FLIGHT(flight_id),
    FOREIGN KEY (crew_id) REFERENCES CREW(crew_id)
);

INSERT INTO FLIGHT_CREW VALUES
('F1','C1','Pilot'),
('F2','C2','CoPilot'),
('F3','C3','Attendant'),
('F4','C4','Pilot'),
('F5','C5','Attendant'),
('F6','C6','Pilot'),
('F7','C7','Attendant');

-- =========================
-- TRIGGERS (7)
-- =========================
DELIMITER $$

CREATE TRIGGER trg_route_check
BEFORE INSERT ON ROUTE
FOR EACH ROW
BEGIN
    IF NEW.departure_airport = NEW.arrival_airport THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid route';
    END IF;
END$$

CREATE TRIGGER trg_dob_check
BEFORE INSERT ON PASSENGER
FOR EACH ROW
BEGIN
    IF NEW.dob > CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid DOB';
    END IF;
END$$

CREATE TRIGGER trg_seat_format
BEFORE INSERT ON SEAT
FOR EACH ROW
BEGIN
    IF NEW.seat_number NOT REGEXP '^[0-9]{1,3}[A-F]$' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid seat format';
    END IF;
END$$

CREATE TRIGGER trg_payment_check
BEFORE INSERT ON PAYMENT
FOR EACH ROW
BEGIN
    IF NEW.amount <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid payment';
    END IF;
END$$

CREATE TRIGGER trg_duplicate_booking
BEFORE INSERT ON BOOKING
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1 FROM BOOKING
        WHERE flight_id = NEW.flight_id
        AND seat_id = NEW.seat_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Seat already booked';
    END IF;
END$$

CREATE TRIGGER trg_flight_time
BEFORE INSERT ON FLIGHT
FOR EACH ROW
BEGIN
    IF NEW.arrival_time <= NEW.departure_time THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid flight time';
    END IF;
END$$
CREATE TRIGGER trg_baggage_weight
BEFORE INSERT ON BAGGAGE
FOR EACH ROW
BEGIN
    IF NEW.weight > 30 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Baggage limit exceeded';
    END IF;
END$$
 
DELIMITER ;