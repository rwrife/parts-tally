import { render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe,toHaveNoViolations } from 'jest-axe';
import { expect,it } from 'vitest';
import App from '../App';
import { MockDeviceTransport } from '../protocol/mockTransport';
expect.extend(toHaveNoViolations);

it('has no automated axe violations before and after authentication',async()=>{const mock=new MockDeviceTransport();const {container}=render(<App transport={mock}/>);expect(await axe(container)).toHaveNoViolations();const user=userEvent.setup();await user.type(screen.getByLabelText(/^Device secret/),'device-secret-123456');await user.click(screen.getByRole('button',{name:'Authenticate and connect'}));await screen.findByText(/Authenticated with device/);expect(await axe(container)).toHaveNoViolations()});
