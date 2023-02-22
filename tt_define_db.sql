drop table if exists geo_object;

create table geo_object (
    geonameid           integer         primary key,
    name                varchar(200),
    asciiname           varchar(200),
    alternatenames      varchar(10000),
    latitude            decimal,
    longitude           decimal,
    feature_class       char(1),
    feature_code        varchar(10),
    country_code        char(2),
    cc2                 char(200),       
    admin1_code         varchar(20),
    admin2_code         varchar(80),
    admin3_code         varchar(20),
    admin4_code         varchar(20),
    population          bigint,
    elevation           integer,
    dem                 integer,
    timezone            varchar(40),
    modification_date   date
);