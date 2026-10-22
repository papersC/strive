// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
interface IVault { function requestAward(uint32,bytes32,uint16,uint16,bytes32) external returns (uint256); }
/// @notice Adversarial token used only in tests: re-enters the vault during transfer.
contract ReentrantToken is ERC20 {
    IVault public vault; bytes32 public pid; bool public armed;
    constructor() ERC20("Evil", "EVL") {}
    function mint(address to, uint256 a) external { _mint(to, a); }
    function arm(IVault v, bytes32 p) external { vault = v; pid = p; armed = true; }
    function _update(address from, address to, uint256 value) internal override {
        super._update(from, to, value);
        if (armed && from == address(vault)) { armed = false; vault.requestAward(1, pid, 9000, 9000, bytes32(0)); }
    }
}
