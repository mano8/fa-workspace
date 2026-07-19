# Teaching-assignment-client domain policy

`astro-reparto-m8` fronts `reparto-docente-m8` through that service's HTTP
contract only (schemas and version range), never Python source. Keep its
contract metadata synchronized with the client schema and compatibility code;
do not silently widen the service-version range.
