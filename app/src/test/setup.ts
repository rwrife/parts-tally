import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
afterEach(()=>{cleanup();localStorage.clear()});
Object.defineProperty(URL,'createObjectURL',{value:()=> 'blob:test',writable:true});
Object.defineProperty(URL,'revokeObjectURL',{value:()=>undefined,writable:true});
