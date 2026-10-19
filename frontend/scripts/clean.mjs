import {rm} from 'node:fs/promises';
// Only framework-generated output; source files and user data are untouched.
await rm(new URL('../.next',import.meta.url),{recursive:true,force:true});
